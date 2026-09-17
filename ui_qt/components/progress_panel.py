"""Progress panel — slim bar + engine indicator + status line + cancel.

The engine indicator is a small pulsing dot + label that sits above the
progress bar, showing the active processing engine (e.g. "Local · Ollama").
It pulses green when the engine is local (free), amber when it's a cloud API
(may incur costs).  The pulse is a gentle opacity animation so the user
always knows the engine is "live".
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.theme import theme_manager


class _PulsingDot(QLabel):
    """A small coloured dot whose opacity gently pulses via QSS background."""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(10, 10)
        self._on = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(900)  # pulse every ~0.9s
        self._render()

    def set_color(self, color: str) -> None:
        self._color = color
        self._render()

    def _tick(self) -> None:
        self._on = not self._on
        self._render()

    def _render(self) -> None:
        opacity = 1.0 if self._on else 0.35
        # use rgba with alpha to simulate the pulse
        c = self._color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        self.setStyleSheet(
            f"background-color: rgba({r},{g},{b},{opacity});"
            f" border: none; border-radius: 5px;"
        )

    def stop(self) -> None:
        self._timer.stop()


class ProgressPanel(QWidget):
    """Progress bar + engine indicator + status label + cancel button."""

    def __init__(
        self,
        cancel_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cancel_callback = cancel_callback

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # ── engine indicator row (above the bar) ────────────────────────
        engine_row = QHBoxLayout()
        engine_row.setContentsMargins(0, 0, 0, 0)
        engine_row.setSpacing(6)
        self._engine_dot = _PulsingDot(theme_manager.palette.success, self)
        engine_row.addWidget(self._engine_dot)
        self._engine_label = QLabel("Local · Ollama")
        self._engine_label.setStyleSheet(
            f"color: {theme_manager.palette.success}; font-size: 11px;"
            f" font-weight: 600; background: transparent;"
        )
        engine_row.addWidget(self._engine_label)
        engine_row.addStretch()
        self._engine_widget = QWidget()
        self._engine_widget.setLayout(engine_row)
        lay.addWidget(self._engine_widget)

        # ── bar + percent ───────────────────────────────────────────────
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(20)  # thicker bar (was 8px)
        self.bar.setObjectName("StripedBar")
        top.addWidget(self.bar, 1)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Caption")
        self.percent_label.setMinimumWidth(38)
        self.percent_label.setAlignment(Qt.AlignRight)
        top.addWidget(self.percent_label)
        lay.addLayout(top)

        # ── status + cancel ─────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(10)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("Muted")
        bottom.addWidget(self.status_label, 1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Compact")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel)
        bottom.addWidget(self.cancel_btn)
        # hidden until an operation starts (clean idle state)
        self.cancel_btn.setVisible(False)
        self.bar.setVisible(False)
        self.percent_label.setVisible(False)
        lay.addLayout(bottom)

    # ── engine indicator ─────────────────────────────────────────────────
    def set_engine(self, label: str, is_local: bool) -> None:
        """Update the pulsing engine indicator.

        ``is_local=True`` → green pulse (free, local).
        ``is_local=False`` → amber pulse (cloud API, may cost).
        """
        p = theme_manager.palette
        color = p.success if is_local else p.warning
        self._engine_dot.set_color(color)
        self._engine_label.setText(label)
        self._engine_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;"
        )

    # ── public API ───────────────────────────────────────────────────────
    def set_value(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, float(fraction)))
        self.bar.setValue(int(fraction * 1000))
        self.percent_label.setText(f"{int(fraction * 100)}%")
        active = fraction > 0.0
        self.bar.setVisible(active or self.cancel_btn.isVisible())
        self.percent_label.setVisible(active or self.cancel_btn.isVisible())

    def set_status(self, text: str, kind: str = "info") -> None:
        """``kind`` ∈ {info, success, warning, error}."""
        p = theme_manager.palette
        color_map = {
            "info": p.text_secondary,
            "success": p.success,
            "warning": p.warning,
            "error": p.error,
        }
        color = color_map.get(kind, p.text_secondary)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 500;"
            " background: transparent;"
        )

    def enable_cancel(self, enabled: bool = True) -> None:
        """Show + enable the cancel button when ``enabled``; hide it when not.

        Also shows/hides the progress bar to match — idle state shows only
        the engine indicator + status label.
        """
        self.cancel_btn.setVisible(enabled)
        self.cancel_btn.setEnabled(enabled)
        self.bar.setVisible(enabled or self.bar.value() > 0)
        self.percent_label.setVisible(enabled or self.bar.value() > 0)

    def reset(self) -> None:
        self.set_value(0.0)
        self.set_status("Ready", "info")
        self.enable_cancel(False)
        # V10.36.0: Clear per-output progress
        self._output_bars = {}
        if hasattr(self, '_output_container'):
            self._output_container.setVisible(False)

    # ── V10.36.0: Per-output progress ────────────────────────────────────

    _output_bars: dict = {}

    def init_output_progress(self, output_keys: list) -> None:
        """Initialize per-output progress bars for the given output keys.

        Called when the output-studio phase starts.  Creates a small
        progress bar + label for each output type.
        """
        from PySide6.QtWidgets import QProgressBar as _QPB
        p = theme_manager.palette

        # Remove old bars if any
        if hasattr(self, '_output_container'):
            self._output_container.deleteLater()

        self._output_container = QWidget()
        ol = QVBoxLayout(self._output_container)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(3)
        self._output_bars = {}

        for key in output_keys:
            row = QHBoxLayout()
            row.setSpacing(6)
            label = QLabel(key.replace("output_", "").replace("_", " ").title())
            label.setStyleSheet(f"color: {p.text_muted}; font-size: 10px; background: transparent;")
            label.setMinimumWidth(100)
            bar = _QPB()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(8)
            bar.setTextVisible(False)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {p.bg_elevated}; border: 1px solid {p.border};"
                f" border-radius: 4px; }}"
                f"QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}"
            )
            row.addWidget(label)
            row.addWidget(bar, 1)
            ol.addLayout(row)
            self._output_bars[key] = bar

        self.layout().addWidget(self._output_container)
        self._output_container.setVisible(True)

    def set_output_progress(self, output_key: str, fraction: float) -> None:
        """Update the progress bar for a specific output (0.0–1.0)."""
        if output_key in self._output_bars:
            self._output_bars[output_key].setValue(int(fraction * 100))

    def _on_cancel(self) -> None:
        if self._cancel_callback:
            self._cancel_callback()
