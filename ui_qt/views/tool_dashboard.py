"""V13.30.0: ToolDashboard — redesigned primary page.

V13.30.0 changes:
  - Reorganized layout per user's UX direction:
    Row 1 (PROCESS):  Full Conversion, Summarization, PDF → Markdown
    Row 2 (TRANSFORM): Translation, Markdown Styler, Packets of Knowledge
    Row 3 (EXTRACT):  OCR Service, PDF/DOCX Cutter, Image Extractor
    Row 4 (AUDIO):    TTS Service, Podcast Maker, Transcribe Service
  - Unique emojis (was: TTS/Podcast/Transcribe all used 🎙️):
    TTS → 🔊, Podcast → 🎙️, Transcribe → 📝
  - Rounder boxes: border-radius 16px (was 10px), primary 20px (was 12px)
  - Internal tools moved to tabs (not cards):
    Output Scanner, Batch Queue, Hallucination Audit → accessed via tab bar
  - Category labels simplified (4 categories instead of 6)

Card click behavior unchanged — see convert_view.py for routing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.components.tool_card import ToolCard
from ui_qt.theme import theme_manager

# ── Tool card definitions ──────────────────────────────────────────────────
# V13.30.0: Reorganized per user's UX direction.
# Each entry: (key, title, subtitle, icon, category, is_primary)
#
# Layout (4 rows × 3 columns):
#   Row 1 (PROCESS):   Full Conversion, Summarization, PDF → Markdown
#   Row 2 (TRANSFORM): Translation, Markdown Styler, Packets of Knowledge
#   Row 3 (EXTRACT):   OCR Service, PDF/DOCX Cutter, Image Extractor
#   Row 4 (AUDIO):     TTS Service, Podcast Maker, Transcribe Service
#
# Moved to tabs (not cards):
#   - Output Scanner → tab
#   - Batch Queue → tab
#   - Hallucination Audit → tab (also accessible from Packets output)
TOOL_CARDS: list[tuple[str, str, str, str, str, bool]] = [
    # Row 1: Main entry points (PROCESS)
    (
        "full_conversion",
        "Full Conversion",
        "Complete 10-step wizard with all output types",
        "🚀",
        "PROCESS",
        True,
    ),
    (
        "summarization",
        "Summarization",
        "Paste text → get summary + keypoints",
        "Σ",
        "PROCESS",
        False,
    ),
    (
        "pdf_to_markdown",
        "Document → Markdown",
        "AnyDoc/markitdown: PDF/DOCX/EPUB → clean Markdown",
        "📄",
        "PROCESS",
        False,
    ),
    # Row 2: Transform tools
    (
        "translation",
        "Translation",
        "EN ↔ FA translation with auto best-backend",
        "🌐",
        "TRANSFORM",
        False,
    ),
    (
        "markdown_styler",
        "Markdown Styler",
        "Messy notes → clean Obsidian markdown",
        "✨",
        "TRANSFORM",
        False,
    ),
    (
        "packets_tool",
        "Packets of Knowledge",
        "Cluster notes → synthesized knowledge packets",
        "📦",
        "TRANSFORM",
        False,
    ),
    # Row 3: Extraction tools
    (
        "ocr_service",
        "OCR Service",
        "Extract text from PDFs or images with auto-cascade",
        "🔍",
        "EXTRACT",
        False,
    ),
    (
        "pdf_docx_cutter",
        "PDF/DOCX Cutter",
        "Extract a page range from PDF or DOCX",
        "✂️",
        "EXTRACT",
        False,
    ),
    (
        "image_extractor",
        "Image Extractor",
        "Extract all images/charts/tables from books",
        "🖼️",
        "EXTRACT",
        False,
    ),
    # Row 4: Audio tools (next to each other in a row, per user request)
    # V13.31.0 (#6): Podcast Maker now opens as modal (was a tab)
    ("tts_service", "TTS Service", "Text → natural speech audio", "🔊", "AUDIO", False),
    ("podcast_maker", "Podcast Maker", "Script → multi-voice podcast audio", "🎙️", "AUDIO", False),
    (
        "transcribe",
        "Transcribe Service",
        "Video/audio → text transcript + summary",
        "📝",
        "AUDIO",
        False,
    ),
]


class ToolDashboard(QWidget):
    """The primary page — a 4×3 grid of tool cards.

    V13.30.0: Redesigned layout with 4 categorized rows.
    Internal tools (Output Scanner, Batch Queue, Hallucination Audit) are
    accessed via tabs, not cards on this page.

    Signals:
        tool_clicked(str): Emitted when a card is clicked, with the tool key.
        The parent (ConvertView) decides what to do (open dialog, switch tab, etc.).
    """

    tool_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: dict[str, ToolCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 6)
        root.setSpacing(10)

        # ── Card grid ───────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        for i, (key, title, subtitle_text, icon, category, is_primary) in enumerate(TOOL_CARDS):
            row = i // 3
            col = i % 3

            # V13.30.0: Category label above each row (first column only)
            if col == 0:
                cat_label = QLabel(category)
                cat_label.setStyleSheet(
                    f"font-size: 9px; font-weight: 700;"
                    f" color: {theme_manager.palette.text_muted};"
                    f" letter-spacing: 2px;"
                    f" background: transparent; margin-top: 4px;"
                )
                grid.addWidget(cat_label, row * 2, 0, 1, 3)  # span all 3 columns

            card = ToolCard(
                key=key,
                title=title,
                subtitle=subtitle_text,
                icon_source=icon,
                category=category,
                is_primary=is_primary,
            )
            card.clicked.connect(self._on_card_clicked)
            self._cards[key] = card
            grid.addWidget(card, row * 2 + 1, col)

        root.addLayout(grid)
        root.addStretch()

    def _on_card_clicked(self, key: str) -> None:
        self.tool_clicked.emit(key)

    def refresh_theme(self) -> None:
        for card in self._cards.values():
            card.refresh_theme()

    def get_card(self, key: str) -> ToolCard | None:
        return self._cards.get(key)


__all__ = ["ToolDashboard", "TOOL_CARDS"]
