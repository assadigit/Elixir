"""V4.3.0: Output Types modal — quick-access output selection from the
convert screen.

A modal dialog showing every output type as a checkbox, so the user can
toggle outputs without diving into Settings → Output → Output Studio.
Opens via the "output types" icon button on the convert screen.

Reuses the same ``outputs.*`` and ``summarisation.*`` / ``docx.*`` setting
keys as the settings sections, so changes here persist and are reflected
in the settings dialog too.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller import Controller

# (setting_key, label, subtitle, icon_name, default)
# V10.29.0 (Sprint 2.2): Single source of truth — import from the registry.
# Previously this list hardcoded 13 outputs and silently missed the 5
# V10.20.0/V10.21.0 outputs (qa, glossary, patterns, cheatsheet, skill).
# The registry now drives all 4 surfaces (dialog, wizard, settings,
# controller) so they can never drift again.
from core.outputs.registry import get_dialog_outputs as _get_dialog_outputs
from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager

_OUTPUTS = _get_dialog_outputs()


class OutputTypesDialog(QDialog):
    """Modal dialog for selecting output types."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Output Types")
        self.setMinimumSize(500, 480)  # V7.4.0: was 560x580 — compact
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("DialogHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 10)
        hl.setSpacing(10)
        title = QLabel("Output Types")
        title.setObjectName("H2")
        hl.addWidget(title)
        hl.addStretch()
        close_btn = QPushButton("×")
        close_btn.setObjectName("IconBtn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.accept)
        hl.addWidget(close_btn)
        root.addWidget(header)

        subtitle = QLabel(
            "Choose what to generate. Toggles persist across conversions. "
            "Core outputs (top) are always available; Output Studio extras "
            "run after summarization."
        )
        subtitle.setObjectName("Caption")
        subtitle.setWordWrap(True)
        subtitle.setContentsMargins(16, 0, 16, 6)
        root.addWidget(subtitle)

        # ── Scrollable checkbox grid ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        sl = QVBoxLayout(scroll_content)
        sl.setContentsMargins(16, 6, 16, 10)
        sl.setSpacing(8)

        self._checkboxes: dict = {}
        # V7.6.0 R1: sort outputs by time cost (least → most intensive)
        # so the user sees the cheap ones first and can decide based on
        # their time constraints.
        from core.pipeline.output_time_estimates import sort_outputs_by_cost

        sorted_outputs = sort_outputs_by_cost(_OUTPUTS)
        for i, (key, label, sub, icon_name, default) in enumerate(sorted_outputs):
            card = self._build_output_card(key, label, sub, icon_name, default)
            sl.addWidget(card)
            if i == 3:  # divider after core outputs
                divider = QLabel("─ Output Studio ─")
                divider.setObjectName("SectionTitle")
                divider.setAlignment(Qt.AlignCenter)
                divider.setContentsMargins(0, 12, 0, 8)
                sl.addWidget(divider)

        # ── Translation section (V4.7.25) ─────────────────────────────
        sl.addWidget(self._build_translation_section())

        sl.addStretch()
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # ── Footer: select all / none + done ──────────────────────────
        footer = QWidget()
        footer.setObjectName("DialogFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 8, 16, 12)
        fl.setSpacing(8)

        select_all = QPushButton("Select all")
        select_all.setCursor(Qt.PointingHandCursor)
        select_all.clicked.connect(lambda: self._toggle_all(True))
        fl.addWidget(select_all)

        select_none = QPushButton("Clear all")
        select_none.setCursor(Qt.PointingHandCursor)
        select_none.clicked.connect(lambda: self._toggle_all(False))
        fl.addWidget(select_none)

        fl.addStretch()

        # V7.6.0 R1: live total time estimate
        self.total_estimate_label = QLabel("")
        self.total_estimate_label.setObjectName("Caption")
        fl.addWidget(self.total_estimate_label)
        self._update_total_estimate()

        done_btn = QPushButton("Done")
        done_btn.setObjectName("Primary")
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setMinimumWidth(100)
        done_btn.clicked.connect(self.accept)
        fl.addWidget(done_btn)
        root.addWidget(footer)

    def _build_output_card(
        self, key: str, label: str, subtitle: str, icon_name: str, default: bool
    ) -> QWidget:
        """Build a single output-type row: icon + label + subtitle + checkbox."""
        p = theme_manager.palette
        card = QFrame()
        card.setObjectName("OutputTypeCard")
        card.setStyleSheet(f"""
            QFrame#OutputTypeCard {{
                background: {p.bg_surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px;
            }}
            QFrame#OutputTypeCard:hover {{
                border-color: {p.border_strong};
            }}
        """)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon(icon_name, p.accent, 20).pixmap(20, 20))
        lay.addWidget(icon_lbl)

        # Label + subtitle
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name = QLabel(label)
        name.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {p.text_primary}; background: transparent;"
        )
        text_col.addWidget(name)
        sub = QLabel(subtitle)
        sub.setStyleSheet(f"font-size: 11px; color: {p.text_muted}; background: transparent;")
        text_col.addWidget(sub)
        lay.addLayout(text_col, 1)

        # Checkbox
        checked = self.controller.get_setting(key, default)
        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
        cb.toggled.connect(self._update_total_estimate)
        lay.addWidget(cb)
        self._checkboxes[key] = cb

        # V7.7.0: cost-tier badge (label only, no minutes — see output_time_estimates)
        from core.pipeline.output_time_estimates import (
            get_output_estimate,
            get_tier_color,
            get_tier_desc,
            get_tier_label,
        )

        est = get_output_estimate(key)
        tier_color_name = get_tier_color(est["tier"])
        # Map tier color name to actual palette color
        color_map = {
            "success": p.success,
            "info": p.info,
            "warning": p.warning,
            "error": p.error,
            "text_muted": p.text_muted,
        }
        badge_color = color_map.get(tier_color_name, p.text_muted)
        tier_label = get_tier_label(est["tier"])
        badge = QLabel(tier_label)
        badge.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {badge_color};"
            f" background: {p.bg_elevated}; padding: 3px 8px;"
            f" border-radius: 8px;"
        )
        # Tooltip: tier description + specific note
        tier_desc = get_tier_desc(est["tier"])
        tooltip = tier_desc
        if est.get("note"):
            tooltip += f"\n{est['note']}"
        badge.setToolTip(tooltip)
        lay.addWidget(badge)

        return card

    def _toggle_all(self, state: bool) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(state)
        self._update_total_estimate()

    # V7.7.0: live load-grade total (tier-based, no minutes)
    def _update_total_estimate(self) -> None:
        """Compute the load grade for all checked outputs + display."""
        from core.pipeline.output_time_estimates import get_load_grade

        enabled_keys = [k for k, cb in self._checkboxes.items() if cb.isChecked()]
        grade = get_load_grade(enabled_keys)
        p = theme_manager.palette
        color_map = {
            "success": p.success,
            "info": p.info,
            "warning": p.warning,
            "error": p.error,
            "text_muted": p.text_muted,
        }
        color = color_map.get(grade["color"], p.text_muted)
        if not enabled_keys:
            self.total_estimate_label.setText("No extra outputs selected")
            self.total_estimate_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 10px;"
            )
        else:
            self.total_estimate_label.setText(f"⚙  {grade['label']}")
            self.total_estimate_label.setStyleSheet(
                f"color: {color}; background: transparent; font-size: 11px; font-weight: 600;"
            )

    def _build_translation_section(self) -> QWidget:
        """Build the translation (EN ↔ FA) section for per-output translation selection."""
        p = theme_manager.palette

        container = QFrame()
        container.setObjectName("TranslationSection")
        container.setStyleSheet(f"""
            QFrame#TranslationSection {{
                background: {p.accent_soft};
                border: 1px solid {p.border_strong};
                border-radius: 8px;
                padding: 6px;
            }}
        """)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # Section header
        header = QLabel("🌐  Translation (EN ↔ FA)")
        header.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {p.accent}; background: transparent;"
        )
        lay.addWidget(header)

        # Master toggle + target language
        row = QHBoxLayout()
        row.setSpacing(8)
        self._tr_enabled_cb = QCheckBox("Translate selected outputs after conversion")
        self._tr_enabled_cb.setChecked(
            bool(self.controller.get_setting("translation.enabled", False))
        )
        self._tr_enabled_cb.setStyleSheet("font-size: 11px; background: transparent;")
        row.addWidget(self._tr_enabled_cb)
        row.addStretch()

        lang_label = QLabel("Target:")
        lang_label.setStyleSheet("font-size: 11px; background: transparent;")
        row.addWidget(lang_label)
        self._tr_lang_combo = QComboBox()
        self._tr_lang_combo.addItem("Farsi", "fa")
        self._tr_lang_combo.addItem("English", "en")
        current_lang = self.controller.get_setting("translation.default_target_lang", "fa")
        idx = self._tr_lang_combo.findData(current_lang)
        if idx >= 0:
            self._tr_lang_combo.setCurrentIndex(idx)
        row.addWidget(self._tr_lang_combo)
        lay.addLayout(row)

        # Per-output translation checkboxes
        outputs_label = QLabel("Which outputs to translate:")
        outputs_label.setStyleSheet(
            "font-size: 10px; color: palette(text-muted); background: transparent;"
        )
        lay.addWidget(outputs_label)

        self._tr_checkboxes: dict = {}
        from ui_qt.settings.translation_page import _TRANSLATABLE_OUTPUTS

        for key, label, _subtitle in _TRANSLATABLE_OUTPUTS:
            cb = QCheckBox(f"{label}")
            cb.setChecked(bool(self.controller.get_setting(f"translation.outputs.{key}", False)))
            cb.setStyleSheet("font-size: 10px; background: transparent;")
            lay.addWidget(cb)
            self._tr_checkboxes[key] = cb

        return container

    def accept(self) -> None:
        """Save all checkbox states to settings on close."""
        for key, cb in self._checkboxes.items():
            self.controller.update_setting(key, cb.isChecked())
        # Save translation settings
        self.controller.update_setting("translation.enabled", self._tr_enabled_cb.isChecked())
        self.controller.update_setting(
            "translation.default_target_lang", self._tr_lang_combo.currentData()
        )
        for key, cb in self._tr_checkboxes.items():
            self.controller.update_setting(f"translation.outputs.{key}", cb.isChecked())
        super().accept()
