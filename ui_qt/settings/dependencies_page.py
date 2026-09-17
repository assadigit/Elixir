"""V4.7.0: Dependencies dashboard — live health check for all libraries,
engines, and system binaries.

A new "Dependencies" head group in Settings showing every dependency with
a **pulsing green/red circle** (animated via QPropertyAnimation). The
dashboard runs all checks on load and on "Recheck" button click.

Categories:
  1. **Core Libraries** — PySide6, torch, transformers, numpy, etc.
  2. **TTS Engines** — Kokoro, NeuTTS-Air, Piper, misaki, llama-cpp
  3. **System Binaries** — Ollama, Piper binary, ffmpeg, Tesseract, Poppler
  4. **Optional** — pyenchant, detectron2, camelot, pymupdf

Each row: [pulsing circle] [name] [status text] [version/path]
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QVariantAnimation,
)
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.system.dependency_checker import DependencyStatus
from core.system.dependency_checker import DetailedDependencyChecker as DependencyChecker

# ── Animated status dot ───────────────────────────────────────────────────

class StatusDot(QLabel):
    """A pulsing circle indicator for dependency status.

    * **Green + pulsing** = required + OK
    * **Red + pulsing** = required + missing
    * **Gray (static)** = optional + missing
    * **Green (static)** = optional + OK
    """

    def __init__(self, status: DependencyStatus, parent: QWidget | None = None) -> None:
        super().__init__("●", parent)
        self._status = status
        self._base_opacity = 1.0
        self._pulse_animation: QVariantAnimation = None

        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"font-size: 22px; color: {self._color()};")

        # Pulsing animation for required dependencies (green or red)
        if status.required:
            self._start_pulse()

    def _color(self) -> str:
        """Return the color for this dot's status."""
        if self._status.is_ok:
            return "#22c55e"  # green-500
        elif self._status.is_optional_missing:
            return "#9ca3af"  # gray-400
        else:
            return "#ef4444"  # red-500

    def _start_pulse(self) -> None:
        """Start a pulsing opacity animation (the 'beeping' effect)."""
        self._pulse_animation = QVariantAnimation(self)
        self._pulse_animation.setDuration(1200)  # 1.2s per cycle
        self._pulse_animation.setStartValue(0.4)
        self._pulse_animation.setEndValue(1.0)
        self._pulse_animation.setLoopCount(-1)  # infinite

        # Easing curve: in-out sine for a smooth breathe effect
        from PySide6.QtCore import QEasingCurve
        self._pulse_animation.setEasingCurve(
            QEasingCurve.Type.InOutSine
        )

        # Toggle between fade-in and fade-out each loop
        self._pulse_animation.valueChanged.connect(self._on_pulse)
        self._pulse_animation.finished.connect(self._reverse_direction)
        self._pulse_animation.start()

    def _on_pulse(self, value: float) -> None:
        """Update the dot's opacity during the pulse animation."""
        color = self._color()
        # Use alpha in the color string for opacity effect
        alpha = int(value * 255)
        self.setStyleSheet(
            f"font-size: 22px; color: {color};"
        )
        # For opacity, we use a QGraphicsOpacityEffect-style approach
        # But since QLabel doesn't have opacity directly, we use color alpha
        self._base_opacity = value

    def _reverse_direction(self) -> None:
        """Reverse the animation direction for the breathe effect."""
        if self._pulse_animation:
            start = self._pulse_animation.startValue()
            end = self._pulse_animation.endValue()
            self._pulse_animation.setStartValue(end)
            self._pulse_animation.setEndValue(start)
            self._pulse_animation.start()

    def stop_pulse(self) -> None:
        """Stop the pulsing animation."""
        if self._pulse_animation:
            self._pulse_animation.stop()
            self._pulse_animation = None


# ── Dependency row ────────────────────────────────────────────────────────

class DependencyRow(QWidget):
    """One row in the dashboard: dot + name + status + version/path."""

    def __init__(self, status: DependencyStatus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._dot = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)

        # Status dot
        self._dot = StatusDot(status)
        lay.addWidget(self._dot)

        # Name + status text
        info_col = QVBoxLayout()
        info_col.setSpacing(0)

        name_label = QLabel(status.name)
        name_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; background: transparent;"
        )
        info_col.addWidget(name_label)

        status_text = status.status_text
        if status.version:
            status_text += f"  ·  v{status.version}"
        elif status.path:
            status_text += f"  ·  {status.path}"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            "font-size: 11px; color: #888; background: transparent;"
        )
        info_col.addWidget(status_label)

        lay.addLayout(info_col, 1)

        # Category badge
        cat_label = QLabel(status.category)
        cat_label.setStyleSheet(
            "font-size: 10px; color: #aaa; background: rgba(0,0,0,0.05);"
            "padding: 2px 8px; border-radius: 8px;"
        )
        lay.addWidget(cat_label)

        # Required/optional badge
        req_label = QLabel("required" if status.required else "optional")
        req_color = "#666" if status.required else "#aaa"
        req_label.setStyleSheet(
            f"font-size: 10px; color: {req_color}; background: transparent;"
        )
        lay.addWidget(req_label)


# ── Main dependencies section ─────────────────────────────────────────────

class DependenciesSection(QGroupBox):
    """The full dependencies dashboard with categorized sections + recheck."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Dependencies & Engines", parent)
        self.controller = controller
        self._dots: list[StatusDot] = []

        # Main layout with scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Summary bar
        self.summary_label = QLabel("Checking dependencies…")
        self.summary_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; padding: 8px 12px;"
            "background: rgba(0,0,0,0.03); border-radius: 6px;"
        )
        outer.addWidget(self.summary_label)

        # Recheck button
        btn_row = QHBoxLayout()
        self.recheck_btn = QPushButton("🔄  Recheck all")
        self.recheck_btn.setCursor(Qt.PointingHandCursor)
        self.recheck_btn.clicked.connect(self._recheck)
        btn_row.addWidget(self.recheck_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # Scrollable area for the dependency rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(2)
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, 1)

        # Initial check
        self._recheck()

    def _recheck(self) -> None:
        """Run all dependency checks and rebuild the dashboard."""
        # Stop existing pulsing animations
        for dot in self._dots:
            dot.stop_pulse()
        self._dots.clear()

        # Clear the layout
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Run all checks
        checker = DependencyChecker()
        results = checker.check_all()

        # Group by category
        categories: dict = {
            "core": ("Core Libraries", []),
            "tts": ("TTS Engines & Models", []),
            "binary": ("System Binaries", []),
            "optional": ("Optional", []),
        }
        for status in results:
            if status.category in categories:
                categories[status.category][1].append(status)

        # Build sections
        required_ok = 0
        required_total = 0
        for cat_key, (cat_label, cat_statuses) in categories.items():
            if not cat_statuses:
                continue
            # Category header
            header = QLabel(f"  {cat_label}")
            header.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #888;"
                "text-transform: uppercase; letter-spacing: 1px;"
                "padding: 8px 4px 4px 4px; background: transparent;"
            )
            self._content_layout.addWidget(header)

            for status in cat_statuses:
                row = DependencyRow(status)
                self._content_layout.addWidget(row)
                if status.required:
                    required_total += 1
                    if status.is_ok:
                        required_ok += 1
                # Track dots for cleanup
                if row._dot:
                    self._dots.append(row._dot)

        self._content_layout.addStretch()

        # Update summary
        if required_ok == required_total:
            self.summary_label.setText(
                f"✅  All required dependencies connected "
                f"({required_ok}/{required_total})"
            )
            self.summary_label.setStyleSheet(
                "font-size: 13px; font-weight: 600; padding: 8px 12px;"
                "background: rgba(34,197,94,0.1); border-radius: 6px;"
                "color: #16a34a;"
            )
        else:
            missing = required_total - required_ok
            self.summary_label.setText(
                f"⚠️  {missing} required dependency(ies) missing "
                f"({required_ok}/{required_total} connected)"
            )
            self.summary_label.setStyleSheet(
                "font-size: 13px; font-weight: 600; padding: 8px 12px;"
                "background: rgba(239,68,68,0.1); border-radius: 6px;"
                "color: #dc2626;"
            )

    def save(self) -> None:
        pass  # read-only dashboard

    def reload(self) -> None:
        self._recheck()
