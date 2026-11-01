"""M2 (UI/UX redesign): the fixed compact left sidebar — the primary nav.

Built entirely on the M1 dashboard primitives (``SectionLabel`` +
``SidebarNavItem`` from ``dashboard_primitives.py``): a data-driven nav
rail (``NAV_GROUPS`` + ``NAV_FOOTER``) inside a fixed, always-visible
~210 px rail (spec §5; user decision Q1 — the Audio group is IN).

Navigation ROUTING is intentionally NOT implemented here, exactly like
the primitives' own contract: items emit ``navigate(key)`` and
``ElixirWindow`` decides what a click means (page switch, tool-dialog
dispatch via the existing ``convert_view`` tool-key dispatch, or one of
the two dialogs).

The experimental destinations (decision Q2 — Queue, Output Scanner,
Bullet Audit, Hallucination Audit) are deliberately ABSENT from
``NAV_GROUPS`` / ``NAV_FOOTER``; they stay reachable via the About &
System "Experimental tools…" fallback and their existing routing.
``EXPERIMENTAL_KEYS`` is the pin anchor for that absence (the views and
their code are intact — hidden, not removed).

Styling: the rail chrome is the ``QFrame#SidebarRail`` QSS rule in
``theme.py``; every item/group label is token-driven (no colour
literals — the M1 zero-literal census covers this file).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.dashboard_primitives import SectionLabel, SidebarNavItem

# The fixed rail width (spec §5 "compact and fixed"; QA budget 200–220 px).
SIDEBAR_WIDTH = 210

# ── Navigation data (the single source of truth for the sidebar IA) ─────────
# Group label ``None`` = ungrouped items (Home at the top; Settings/About in
# the footer).  Labels are the EXACT user-facing names verified against
# ``tool_dashboard.TOOL_CARDS`` + the M0 §5 inventory (never renamed).
NAV_GROUPS: list[tuple[str | None, list[tuple[str, str, str]]]] = [
    (None, [("home", "home", "Home")]),
    (
        "Processing",
        [
            ("summarization", "sigma", "Summarization"),
            ("pdf_to_markdown", "file-text", "Document → Markdown"),
            ("translation", "globe", "Translation"),
        ],
    ),
    (
        "Utilities",
        [
            ("markdown_styler", "sparkles", "Markdown Styler"),
            ("packets_tool", "layers", "Packets of Knowledge"),
            ("ocr_service", "scan", "OCR Service"),
            ("pdf_docx_cutter", "scissors", "PDF/DOCX Cutter"),
            ("image_extractor", "image", "Image Extractor"),
        ],
    ),
    (
        "Audio",
        [
            ("tts_service", "audio-lines", "TTS Service"),
            ("podcast_maker", "mic", "Podcast Maker"),
            ("transcribe", "headphones", "Transcribe Service"),
        ],
    ),
]

# Pinned below the scrollable groups — always visible even at min height.
NAV_FOOTER: list[tuple[str, str, str]] = [
    ("settings", "settings", "Settings"),
    ("about", "info", "About"),
]

# Decision Q2: these destinations NEVER appear in the sidebar nav data.
# (Their views + routing stay intact behind About & System.)
EXPERIMENTAL_KEYS = ("batch_queue", "output_scanner", "quarantine", "hallucination_audit")


def nav_keys() -> list[str]:
    """Every navigation key the sidebar can emit (groups + footer)."""
    keys: list[str] = []
    for _group, items in NAV_GROUPS:
        keys.extend(key for key, _icon, _label in items)
    keys.extend(key for key, _icon, _label in NAV_FOOTER)
    return keys


class Sidebar(QFrame):
    """The fixed compact left rail: icons + labels, grouped, always visible.

    Emits ``navigate(key)`` on click (routing belongs to the window) and
    tracks the active destination via ``set_active`` (the restrained
    accent treatment from the primitives).  The grouped list scrolls
    vertically at short window heights; the Settings/About footer stays
    pinned below it.
    """

    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarRail")
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._items: dict[str, SidebarNavItem] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 10, 0, 10)
        root.setSpacing(6)

        # ── scrollable grouped nav ────────────────────────────────────
        nav_host = QWidget()
        nav = QVBoxLayout(nav_host)
        nav.setContentsMargins(10, 0, 10, 0)
        nav.setSpacing(2)
        for group_label, items in NAV_GROUPS:
            if group_label is not None:
                nav.addSpacing(8)
                nav.addWidget(SectionLabel(group_label))
            for key, icon_name, label in items:
                item = SidebarNavItem(icon_name, label)
                item.clicked.connect(lambda k=key: self.navigate.emit(k))
                self._items[key] = item
                nav.addWidget(item)
        nav.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(nav_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # ScrollBarPolicy is a Qt-namespace enum — it is NOT exposed as a
        # QScrollArea class attribute on PySide6 >= 6.11 (AttributeError at
        # launch on the user's Windows run, V0.6.70 pre-release smoke), so
        # the address must be Qt.ScrollBarPolicy.* (Shape above IS a QFrame
        # class enum and stays as-is).
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root.addWidget(scroll, 1)

        # ── pinned footer (Settings / About) ──────────────────────────
        divider = QFrame()
        divider.setObjectName("Divider")
        root.addWidget(divider)
        footer = QVBoxLayout()
        footer.setContentsMargins(10, 0, 10, 0)
        footer.setSpacing(2)
        for key, icon_name, label in NAV_FOOTER:
            item = SidebarNavItem(icon_name, label)
            item.clicked.connect(lambda k=key: self.navigate.emit(k))
            self._items[key] = item
            footer.addWidget(item)
        root.addLayout(footer)

    # ── state ───────────────────────────────────────────────────────────
    def set_active(self, key: str | None) -> None:
        """Mark ``key`` as the current destination (None clears all)."""
        for k, item in self._items.items():
            item.set_active(k == key)

    # ── theme ───────────────────────────────────────────────────────────
    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles (theme toggle hook)."""
        for item in self._items.values():
            item.refresh_theme()
        # SectionLabel + the rail chrome are QSS-driven — nothing to redo.


__all__ = ["Sidebar", "NAV_GROUPS", "NAV_FOOTER", "EXPERIMENTAL_KEYS", "SIDEBAR_WIDTH", "nav_keys"]
