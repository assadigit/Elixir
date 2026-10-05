"""Shared helpers for settings tabs — consistent labelled-row builders."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)


def make_form() -> QFormLayout:
    """A tidy form layout with consistent, compact label/field spacing."""
    f = QFormLayout()
    f.setContentsMargins(0, 2, 0, 2)
    f.setHorizontalSpacing(12)
    f.setVerticalSpacing(6)
    # NOTE: combining AlignRight | AlignVCenter via | is invalid in PySide6
    # 6.11 (causes RecursionError). Use a single alignment flag instead.
    f.setLabelAlignment(Qt.AlignRight)
    f.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
    return f


def labeled_checkbox(text: str, checked: bool = False, tooltip: str = "") -> QCheckBox:
    cb = QCheckBox(text)
    cb.setChecked(checked)
    if tooltip:
        cb.setToolTip(tooltip)
    return cb


def labeled_combo(values: list, current: str = "", tooltip: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems([str(v) for v in values])
    if current:
        idx = cb.findText(str(current))
        if idx >= 0:
            cb.setCurrentIndex(idx)
    if tooltip:
        cb.setToolTip(tooltip)
    return cb


def labeled_spin(
    value: int, minimum: int = 0, maximum: int = 100000, suffix: str = "", tooltip: str = ""
) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(minimum, maximum)
    sb.setValue(int(value))
    if suffix:
        sb.setSuffix(suffix)
    if tooltip:
        sb.setToolTip(tooltip)
    return sb


def labeled_line(
    text: str = "", placeholder: str = "", password: bool = False, tooltip: str = ""
) -> QLineEdit:
    le = QLineEdit(text)
    if placeholder:
        le.setPlaceholderText(placeholder)
    if password:
        le.setEchoMode(QLineEdit.Password)
    if tooltip:
        le.setToolTip(tooltip)
    return le
