"""V0.6.69 — LocalLLMLights: the top-bar status lights for local LLM servers.

The UI half of the 2026-10-26 field report ("show a green light that shows
whether ollama or any other locally famous LLM client is on or not …
actively look for ollama or llama.cpp server as they're online"). The
probe half lives in :mod:`core.system.local_llm_monitor` (Qt-free, never
raises); this widget only RENDERS verdicts handed to it — all probing and
the QTimer cadence belong to ``ElixirWindow`` (the window owns the poll
loop so the widget stays trivially testable and never owns threads).

One chip per locally-famous client — **Ollama**, **llama.cpp**,
**LM Studio** — a colored dot plus (when the top bar has room) the
client's name:

* **green**  — the server answered; it is ON.
* **gray**   — not running (an ordinary state, NOT an error: the whole
  point of V0.6.69 is that a missing local server must never nag).
* **amber**  — the very first probe is still in flight ("checking…").

Hovering a chip shows the verdict + endpoint (+ the probed llama.cpp port
order when offline). The widget is WIDTH-ADAPTIVE because the top bar is
full (brand, tagline, Wizard/Merge buttons, theme/about/settings): it
renders the richest mode that fits the budget the window hands it —

* ``full`` — dot + name per client (wide windows / maximized);
* ``dots`` — dots only, names move into the tooltips (default width);
* ``mini`` — one aggregate dot whose tooltip lists every client (tiny
  windows; still answers "is ANY local LLM on?" at a glance).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core.system.local_llm_monitor import (
    LLAMACPP_KEY,
    LMSTUDIO_KEY,
    OLLAMA_KEY,
    LocalLLMStatus,
)
from ui_qt.theme import theme_manager

logger = logging.getLogger(__name__)

# Display order (mirrors core.system.local_llm_monitor's probe order).
_CHIP_ORDER = (OLLAMA_KEY, LLAMACPP_KEY, LMSTUDIO_KEY)
_CHIP_NAMES = {
    OLLAMA_KEY: "Ollama",
    LLAMACPP_KEY: "llama.cpp",
    LMSTUDIO_KEY: "LM Studio",
}

MODE_FULL = "full"
MODE_DOTS = "dots"
MODE_MINI = "mini"

_PENDING_TIP = (
    "Elixir is checking whether local LLM servers are running\n(Ollama, llama.cpp, LM Studio)…"
)
_POLL_NOTE = "\n(status re-checked every few seconds)"


class LocalLLMLights(QWidget):
    """Adaptive per-client status lights (see module docstring)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LocalLLMLights")
        # Transparent background — the top bar paints the chrome.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent;")
        self.setToolTip(_PENDING_TIP)
        self.setAccessibleName("Local LLM server status lights")

        self._statuses: list[LocalLLMStatus] = []
        self._mode = MODE_FULL  # the real mode is chosen by the first set_budget()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._chips: dict[str, dict[str, QLabel]] = {}
        for key in _CHIP_ORDER:
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFixedWidth(16)
            name = QLabel(_CHIP_NAMES[key])
            self._chips[key] = {"dot": dot, "name": name}
            lay.addWidget(dot)
            lay.addWidget(name)

        # The MINI-mode aggregate dot (kept in the layout, hidden otherwise).
        self._agg_dot = QLabel("●")
        self._agg_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agg_dot.setFixedWidth(16)
        lay.insertWidget(0, self._agg_dot)

        self._apply_colors()  # amber "checking…" until the first verdict lands

    # ── public API ───────────────────────────────────────────────────────

    def apply_statuses(self, statuses: list[LocalLLMStatus]) -> None:
        """Render a fresh probe verdict (called on the main thread by the
        window's poll loop). Tolerates anything — an odd payload just
        leaves the previous state painted."""
        try:
            if statuses is not None:
                self._statuses = list(statuses)
            self._apply_colors()
        except Exception:
            logger.debug("llm-lights status apply failed", exc_info=True)

    def refresh_theme(self) -> None:
        """Re-paint with the current palette (theme toggle)."""
        self._apply_colors()

    def set_budget(self, width: int) -> None:
        """Pick the richest display mode that fits ``width`` pixels (the
        window measures its top bar and calls this on every resize)."""
        try:
            widths = self.mode_widths()
            mode = MODE_FULL
            for candidate in (MODE_FULL, MODE_DOTS, MODE_MINI):
                if width >= widths[candidate]:
                    mode = candidate
                    break
            else:  # pragma: no cover — mini always fits
                mode = MODE_MINI
            if mode != self._mode:
                self._set_mode(mode)
        except Exception:
            logger.debug("llm-lights budget adapt failed", exc_info=True)

    def current_mode(self) -> str:
        """The active display mode (tests + the window's smoke checks)."""
        return self._mode

    # ── rendering ────────────────────────────────────────────────────────

    def _by_key(self, key: str) -> LocalLLMStatus | None:
        for s in self._statuses:
            if s.key == key:
                return s
        return None

    def _apply_colors(self) -> None:
        p = theme_manager.palette
        pending = not self._statuses
        for key in _CHIP_ORDER:
            chip = self._chips[key]
            status = self._by_key(key)
            if pending or status is None:
                color = p.warning
                tip = _PENDING_TIP
                acc = f"{_CHIP_NAMES[key]} status: checking…"
            elif status.online:
                color = p.success
                tip = status.tooltip + _POLL_NOTE
                acc = f"{_CHIP_NAMES[key]} status: running"
            else:
                color = p.text_secondary
                tip = status.tooltip + _POLL_NOTE
                acc = f"{_CHIP_NAMES[key]} status: not running"
            chip["dot"].setStyleSheet(f"font-size: 15px; color: {color}; background: transparent;")
            chip["name"].setStyleSheet(
                f"font-size: 11px; color: {p.text_secondary}; background: transparent;"
            )
            chip["dot"].setToolTip(tip)
            chip["name"].setToolTip(tip)
            chip["dot"].setAccessibleName(acc)
            chip["name"].setAccessibleName(acc)
        # The aggregate dot: green when ANY client is on, amber while
        # checking, gray when none — with the full list in its tooltip.
        if pending:
            agg_color, agg_acc = p.warning, "Local LLM servers: checking…"
            agg_tip = _PENDING_TIP
        else:
            online = [s for s in self._statuses if s.online]
            if online:
                agg_color, agg_acc = p.success, f"Local LLM servers: {len(online)} running"
            else:
                agg_color, agg_acc = p.text_secondary, "Local LLM servers: none running"
            agg_tip = (
                "Local LLM servers — "
                + (f"{len(online)}/{len(self._statuses) or 1} running")
                + _POLL_NOTE
                + "\n"
                + "\n".join(f"• {s.tooltip}" for s in self._statuses)
            )
        self._agg_dot.setStyleSheet(
            f"font-size: 15px; color: {agg_color}; background: transparent;"
        )
        self._agg_dot.setToolTip(agg_tip)
        self._agg_dot.setAccessibleName(agg_acc)
        self._set_mode(self._mode)  # keep visibility consistent after re-paint

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        full = mode == MODE_FULL
        dots = mode in (MODE_FULL, MODE_DOTS)
        for key in _CHIP_ORDER:
            chip = self._chips[key]
            chip["dot"].setVisible(dots)
            chip["name"].setVisible(full)
        self._agg_dot.setVisible(mode == MODE_MINI)

    # ── measurement ──────────────────────────────────────────────────────

    def mode_widths(self) -> dict[str, int]:
        """The horizontal pixels each mode needs (its sizeHint width),
        measured from the live labels — used by ``set_budget`` and by
        tests to pin the adaptive contract."""
        widths: dict[str, int] = {}
        dots = sum(self._chips[k]["dot"].sizeHint().width() for k in _CHIP_ORDER)
        full = dots + sum(self._chips[k]["name"].sizeHint().width() for k in _CHIP_ORDER)
        # spacing between the visible widgets (6 px per gap; +2 px of
        # margin keep the fit honest against font-metric drift).
        widths[MODE_FULL] = full + 6 * (2 * len(_CHIP_ORDER) - 1) + 2
        widths[MODE_DOTS] = dots + 6 * (len(_CHIP_ORDER) - 1) + 2
        widths[MODE_MINI] = self._agg_dot.sizeHint().width() + 2
        return widths


def build_status_lights() -> tuple[LocalLLMLights | None, Any]:
    """Best-effort factory for the window: returns (lights, None) on
    success, (None, error) on failure — a broken light must never block
    startup (the splash/guard best-effort precedent)."""
    try:
        return LocalLLMLights(), None
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("local-LLM lights unavailable: %s", exc)
        return None, exc
