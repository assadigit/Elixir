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

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Select your PDF and document type")
        title.setObjectName("H2")
        lay.addWidget(title)

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

        # V7.5.0 #8: Configuration profiles — save/load named setting bundles.
        prof_box = QGroupBox("Configuration profiles (optional)")
        prof_lay = QVBoxLayout(prof_box)
        prof_lay.setContentsMargins(10, 10, 10, 8)
        prof_lay.setSpacing(6)
        prof_row = QHBoxLayout()
        prof_row.setSpacing(6)
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Saved configuration profiles (models, outputs, translation, etc.)")
        prof_row.addWidget(self.profile_combo, 1)
        self.prof_save_btn = QPushButton("Save…")
        self.prof_save_btn.setObjectName("Compact")
        self.prof_save_btn.setCursor(Qt.PointingHandCursor)
        self.prof_save_btn.setToolTip("Save the current wizard settings as a named profile")
        self.prof_save_btn.clicked.connect(self._save_profile)
        prof_row.addWidget(self.prof_save_btn)
        self.prof_load_btn = QPushButton("Load")
        self.prof_load_btn.setObjectName("Compact")
        self.prof_load_btn.setCursor(Qt.PointingHandCursor)
        self.prof_load_btn.setToolTip("Apply the selected profile to this wizard session")
        self.prof_load_btn.clicked.connect(self._load_profile)
        prof_row.addWidget(self.prof_load_btn)
        self.prof_del_btn = QPushButton("Delete")
        self.prof_del_btn.setObjectName("Compact")
        self.prof_del_btn.setCursor(Qt.PointingHandCursor)
        self.prof_del_btn.setToolTip("Delete the selected profile")
        self.prof_del_btn.clicked.connect(self._delete_profile)
        prof_row.addWidget(self.prof_del_btn)
        prof_lay.addLayout(prof_row)
        lay.addWidget(prof_box)

        lay.addStretch()

        # Select current source_type
        if self.state.source_type in self._type_cards:
            self._type_cards[self.state.source_type].set_selected(True)
        if self.state.input_path:
            self.pdf_edit.setText(self.state.input_path)
        self._refresh_profiles()

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
                    self, "_show_detection_suggestion",
                    _Qt.ConnectionType.QueuedConnection,
                )
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)  # detection is best-effort; don't block the user

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
            self._detection_label.linkActivated.connect(
                lambda: self._apply_detection(result)
            )
        else:
            self._detection_label.setText(
                f"🔍 Auto-detected: {result.label()} "
                f"({result.confidence:.0%} confidence) — "
                f"keeping default (normal_book)"
            )
            self._detection_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; "
                f"font-size: 11px; padding: 4px;"
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
                f"color: {p.success}; background: transparent; "
                f"font-size: 11px; padding: 4px;"
            )

    # ── V7.5.0 #8: Configuration profiles ─────────────────────────────────
    # Per-book fields (input_path, output_dir, selected_chapters) are excluded
    # so a profile captures the reusable configuration (models, outputs,
    # translation, fine-tuning) without pinning it to one file.
    _PROFILE_EXCLUDE = ("input_path", "output_dir", "selected_chapters")

    def _refresh_profiles(self) -> None:
        """Repopulate the profiles dropdown."""
        from core.pipeline.profiles import list_profiles
        self.profile_combo.clear()
        profiles = list_profiles()
        if not profiles:
            self.profile_combo.addItem("(no saved profiles)")
            self.profile_combo.setEnabled(False)
            self.prof_load_btn.setEnabled(False)
            self.prof_del_btn.setEnabled(False)
        else:
            self.profile_combo.setEnabled(True)
            self.prof_load_btn.setEnabled(True)
            self.prof_del_btn.setEnabled(True)
            for p in profiles:
                self.profile_combo.addItem(p["name"])

    def _save_profile(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from core.pipeline.profiles import save_profile
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        # Serialize current wizard state, excluding per-book fields.
        from dataclasses import asdict
        data = {k: v for k, v in asdict(self.state).items()
                if k not in self._PROFILE_EXCLUDE}
        if save_profile(name, data):
            QMessageBox.information(self, "Profile saved", f"Profile '{name}' saved.")
            self._refresh_profiles()
            # Select the just-saved profile
            idx = self.profile_combo.findText(name)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        else:
            QMessageBox.warning(self, "Save failed", f"Could not save profile '{name}'.")

    def _load_profile(self) -> None:
        from core.pipeline.profiles import load_profile
        name = self.profile_combo.currentText()
        if not name or name == "(no saved profiles)":
            return
        data = load_profile(name)
        if not data:
            QMessageBox.warning(self, "Load failed", f"Could not load profile '{name}'.")
            return
        # Apply each field to self.state (skip per-book + unknown fields).
        applied = 0
        for k, v in data.items():
            if k in self._PROFILE_EXCLUDE:
                continue
            if hasattr(self.state, k):
                try:
                    setattr(self.state, k, v)
                    applied += 1
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
        # Also mirror key settings into the controller so already-built step
        # widgets that read from controller.get_setting() on save_to_state
        # pick up the profile values.
        _STATE_TO_SETTING = {
            "summarisation_model": "summarisation.model",
            "primary_ocr_model": "ocr.primary_model",
            "fast_model": "summarisation.fast_model",
            "max_workers": "summarisation.max_workers",
            "temperature": "summarisation.temperature",
            "translation_backend": "translation.backend",
            "translation_target_lang": "translation.default_target_lang",
            "translation_harakat_model": "translation.harakat_model",
            "coverage_threshold": "summarisation.coverage_threshold",
            "resume_enabled": "summarisation.resume_enabled",
        }
        for sk, setting_key in _STATE_TO_SETTING.items():
            if sk in data:
                self.controller.update_setting(setting_key, data[sk])
        QMessageBox.information(
            self, "Profile loaded",
            f"Profile '{name}' applied ({applied} settings).\n\n"
            "The conversion will use these settings. Step widgets may still\n"
            "show the previous values until you reopen the wizard.",
        )

    def _delete_profile(self) -> None:
        from core.pipeline.profiles import delete_profile
        name = self.profile_combo.currentText()
        if not name or name == "(no saved profiles)":
            return
        ret = QMessageBox.question(
            self, "Delete profile",
            f"Delete profile '{name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        if delete_profile(name):
            self._refresh_profiles()
        else:
            QMessageBox.warning(self, "Delete failed", f"Could not delete profile '{name}'.")

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
            elif sk == "ocr.auto_detect_scanned":
                self.state.auto_detect_scanned = sv
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
