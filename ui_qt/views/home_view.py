"""M2 (UI/UX redesign): the home view — the landing page.

Spec §6 dashboard composition:
1. a concise purpose line,
2. the Full Conversion hero (the single dominant action), and
3. the Quick Tools grid of secondary tools, grouped Processing /
   Utilities / Audio (user decision Q1 — the Audio group is IN) with
   ``SectionLabel`` group headers.

The Quick Tools grid is fed from the EXISTING ``TOOL_CARDS`` data (the
single source of truth for keys / exact user-facing titles / one-line
descriptions), dropping the ``full_conversion`` entry — no duplicate
hero tile (spec §6) — and mapping the legacy PROCESS/TRANSFORM/EXTRACT
categories onto the M2 IA groups. The emoji card icons are swapped for
the M1 Lucide glyph names (spec §7: one outline family, no emoji). The
column count reflows with the available width (spec §6 "grid reflows
with available width"): 4 columns wide, 3 at mid widths, 2 on narrow
windows — the thresholds are re-checked on every resize.

The hero is an editorial split (spec §6): heading + supporting copy + ONE
``QPushButton#HeroPrimary`` "Start Conversion" on the left, the supplied
hero illustration (decision Q5 — ``assets/hero_books_quill.png``) at
reduced size on the right. The illustration's soft alpha halo is
FLATTENED against the hero surface colour (composited, never pasted onto
a different ground), the visual hides at narrow widths (spec §7
"simplify or remove it at narrow widths"), and the final judgement
happens on the user's Windows QA (decision Q5 — if it reads poorly on
the real background there, the spec allows omitting it: do NOT force it).

COPY (spec §6 + §1, verified against real capabilities — nothing invented):

  purpose   "Knowledge, distilled into clarity."               (spec §1)
  heading   "Turn documents into clear, structured knowledge." (spec §6)
  support   "Transform books, articles, and documents into useful
             summaries and structured outputs."                (spec §6)
  CTA       "Start Conversion"       (spec §6 + user decision Q7)

The CTA opens the SAME modal WizardView the removed header button used:
this view only EMITS ``start_requested`` and ``ElixirWindow`` connects it
to its existing ``_open_wizard`` — the opening logic is never forked.
Quick Tool cards likewise only emit ``tool_clicked``; the window routes
them through the existing ``convert_view`` tool-key dispatch.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.dashboard_primitives import QuickToolCard, SectionLabel
from ui_qt.theme import theme_manager
from ui_qt.views.tool_dashboard import TOOL_CARDS

# Hero illustration budget (decision Q5: reduced size — "keep it ≤ ~260 px
# wide"; the source is 632×330, so it always scales down).
_HERO_IMAGE_MAX_W = 260

# The mid-width size bucket (V0.6.71 / M3 QA): at content widths between
# the hide threshold and _HERO_IMAGE_WIDE_W the illustration shrinks to
# this instead of vanishing, so the text column keeps its room.
_HERO_IMAGE_MID_W = 200

# Below this CONTENT width the illustration hides (spec §7 narrow-width
# rule) — aligned with the Quick Tools 3-column threshold (_GRID_3_MIN_W):
# any window that comfortably fits a 3-column tool grid also keeps the
# hero visual. (V0.6.71 / M3 QA: the old 900 px cutoff left the whole
# 760–899 px band — the user's actual Windows run — with NO visual at
# all, which read as "the asset isn't implemented".) The 560 px minimum
# window ≈ 330 px of content (hidden — the text column keeps its room).
_HERO_IMAGE_MIN_VIEW_W = 760

# At/above this content width the illustration is full-size (260 px);
# between the hide threshold and here it uses the mid size above.
_HERO_IMAGE_WIDE_W = 900

# Quick Tools — the M1 Lucide glyph for each tool (spec §7: one outline
# family; the emoji strings from TOOL_CARDS are display-only legacy and
# are NOT consumed here). Key order follows the locked M2 IA (Q1).
_QUICK_ICON: dict[str, str] = {
    "summarization": "sigma",
    "pdf_to_markdown": "file-text",
    "translation": "globe",
    "markdown_styler": "sparkles",
    "packets_tool": "layers",
    "ocr_service": "scan",
    "pdf_docx_cutter": "scissors",
    "image_extractor": "image",
    "tts_service": "audio-lines",
    "podcast_maker": "mic",
    "transcribe": "headphones",
}

# The M2 IA groups (decision Q1): legacy PROCESS/TRANSFORM/EXTRACT map
# onto Processing / Utilities; AUDIO stays Audio. full_conversion is
# deliberately ABSENT (the hero owns it — no duplicate tile, spec §6).
_QUICK_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Processing", ("summarization", "pdf_to_markdown", "translation")),
    (
        "Utilities",
        (
            "markdown_styler",
            "packets_tool",
            "ocr_service",
            "pdf_docx_cutter",
            "image_extractor",
        ),
    ),
    ("Audio", ("tts_service", "podcast_maker", "transcribe")),
]

# Reflow thresholds (spec §6): 4 columns on wide windows, 3 at mid
# widths, 2 on narrow ones (the 560 px minimum window leaves ≈330 px of
# content after the rail — 2 compact columns fit there).
_GRID_4_MIN_W = 1200
_GRID_3_MIN_W = 760


def _project_root() -> Path:
    """The repo root / PyInstaller bundle (the house icons.py pattern)."""
    from app_paths import bundle_dir  # V0.6.63: bundle-aware

    return bundle_dir()


def _tool_meta() -> dict[str, tuple[str, str]]:
    """key → (exact user-facing title, one-line description) from the
    existing TOOL_CARDS data — titles are never re-typed here."""
    return {key: (title, subtitle) for key, title, subtitle, _i, _c, _p in TOOL_CARDS}


class HomeView(QWidget):
    """The M2 landing page: purpose line + the Full Conversion hero
    (+ the Quick Tools grid, added by the grid commit)."""

    start_requested = Signal()
    tool_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Pixmap cache key (bucket, surface) — see _apply_hero_pixmap.
        self._hero_pm_key: tuple | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 10)
        root.setSpacing(14)

        # 1 — the purpose line (spec §6 hierarchy; the spec §1 brand line).
        purpose = QLabel("Knowledge, distilled into clarity.")
        purpose.setObjectName("Support")
        root.addWidget(purpose)

        # 2 — the Full Conversion hero (the single dominant action).
        root.addWidget(self._build_hero())

        # 3 — the Quick Tools section (secondary tools only — the hero is
        # never duplicated as a tile; spec §6 / decision Q7).
        root.addLayout(self._build_quick_tools())

        root.addStretch()

    # ══════════════════════════════════════════════════════════════════════
    # The hero
    # ══════════════════════════════════════════════════════════════════════
    def _build_hero(self) -> QFrame:
        """Editorial split: text + CTA left, illustration right (spec §6).

        A calm surface with subtle separation from the page background —
        the existing ``QFrame#Card`` QSS rule (surface fill + hairline
        border + soft radius), no shadow.
        """
        hero = QFrame()
        hero.setObjectName("Card")
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(24)

        text_col = QVBoxLayout()
        text_col.setSpacing(10)

        heading = QLabel("Turn documents into clear, structured knowledge.")
        heading.setObjectName("Hero")
        heading.setWordWrap(True)
        text_col.addWidget(heading)

        support = QLabel(
            "Transform books, articles, and documents into useful "
            "summaries and structured outputs."
        )
        support.setObjectName("Support")
        support.setWordWrap(True)
        text_col.addWidget(support)

        text_col.addSpacing(6)
        # ONE clear primary action (spec §6). Decision Q7: the header
        # "✨ Process Wizard" button is gone; the hero owns the entry and
        # both landed in the same milestone so the primary entry never
        # gaps. The tooltip is the removed header button's exact copy.
        self.cta_btn = QPushButton("Start Conversion")
        self.cta_btn.setObjectName("HeroPrimary")
        self.cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta_btn.setToolTip("Open the guided step-by-step conversion wizard")
        self.cta_btn.clicked.connect(self.start_requested.emit)
        text_col.addWidget(self.cta_btn, 0, Qt.AlignmentFlag.AlignLeft)
        text_col.addStretch()

        lay.addLayout(text_col, 1)

        # The illustration (decision Q5) — flattened against the surface,
        # hidden at narrow widths (spec §7).
        self._hero_visual = QLabel()
        self._hero_visual.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lay.addWidget(self._hero_visual, 0, Qt.AlignmentFlag.AlignVCenter)
        self._apply_hero_pixmap()

        return hero

    # ── the hero illustration (decision Q5) ──────────────────────────────
    def _flattened_hero_pixmap(self, max_w: int):
        """The supplied illustration scaled to ≤ ``max_w`` px wide with its
        alpha flattened onto the CURRENT hero surface colour.

        The asset is 632×330 RGBA with a soft halo quarter (the M1
        inspection): pasting it straight onto a different ground would
        leave a pale rectangle. Compositing against the exact surface
        token keeps the halo invisible in BOTH themes — and is why
        ``refresh_theme`` re-runs this instead of caching one pixmap.
        """
        from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

        src_path = _project_root() / "assets" / "hero_books_quill.png"
        if not src_path.exists():
            return None  # asset absent (thin bundles) → text-only hero
        src = QPixmap(str(src_path))
        if src.isNull():
            return None
        w = min(max_w, src.width())
        h = max(1, round(src.height() * w / src.width()))
        flat = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        flat.fill(QColor(theme_manager.palette.bg_surface))
        painter = QPainter(flat)
        painter.drawPixmap(
            0,
            0,
            src.scaled(
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        painter.end()
        return QPixmap.fromImage(flat)

    def _apply_hero_pixmap(self) -> None:
        """(Re)composite the illustration at the size bucket the current
        width supports, then apply the narrow-width hide rule.

        V0.6.71 (M3 QA): full 260 px at wide widths, 200 px at mid widths —
        the old binary hide-at-900 left the 3-column-grid band with no
        visual at all, which read on the user's Windows run as "the asset
        isn't implemented". The pixmap is cached per (bucket, surface) so
        a resize drag only recomposites on bucket or theme crossings.
        """
        budget = _HERO_IMAGE_MAX_W if self.width() >= _HERO_IMAGE_WIDE_W else _HERO_IMAGE_MID_W
        key = (budget, theme_manager.palette.bg_surface)
        if key != self._hero_pm_key:
            pm = self._flattened_hero_pixmap(budget)
            if pm is None:
                self._hero_pm_key = ("missing",)
                self._hero_visual.setVisible(False)
                return
            self._hero_visual.setPixmap(pm)
            self._hero_pm_key = key
        self._hero_visual.setVisible(self.width() >= _HERO_IMAGE_MIN_VIEW_W)

    # ══════════════════════════════════════════════════════════════════════
    # The Quick Tools grid (spec §6: compact, consistent, reflowing)
    # ══════════════════════════════════════════════════════════════════════
    def _build_quick_tools(self) -> QVBoxLayout:
        """The Quick Tools section: a "Quick Tools" section heading, then
        per-group ``SectionLabel`` headers + ``QuickToolCard`` rows fed
        from TOOL_CARDS (minus full_conversion), reflowing with width."""
        section = QVBoxLayout()
        section.setSpacing(10)

        head = QLabel("Quick Tools")
        head.setObjectName("SectionHead")
        section.addWidget(head)

        self._quick_cards: list[QuickToolCard] = []
        self._quick_headers: list[SectionLabel] = []
        self._quick_grid = QGridLayout()
        self._quick_grid.setSpacing(10)
        self._grid_cols = 0  # forces the first _relayout to lay everything out
        meta = _tool_meta()
        for group_label, keys in _QUICK_GROUPS:
            self._quick_headers.append(SectionLabel(group_label))
            for key in keys:
                title, subtitle = meta[key]
                card = QuickToolCard(
                    key, title, description=subtitle, icon_name=_QUICK_ICON[key]
                )
                card.clicked.connect(self.tool_clicked.emit)
                self._quick_cards.append(card)
        section.addLayout(self._quick_grid)
        self._relayout_quick_grid()
        return section

    def _relayout_quick_grid(self) -> None:
        """(Re)place the group headers + cards into the grid at the column
        count the current width supports. Headers and cards are persistent
        widgets — they are re-added, never rebuilt (click routing + focus
        live on the card, so a reflow loses nothing)."""
        width = max(self.width(), 1)
        cols = 4 if width >= _GRID_4_MIN_W else (3 if width >= _GRID_3_MIN_W else 2)
        if cols == self._grid_cols:
            return
        self._grid_cols = cols
        while self._quick_grid.count():
            self._quick_grid.takeAt(0)  # items only — the widgets survive
        row = 0
        cards = {card.key: card for card in self._quick_cards}
        for header, (_group_label, keys) in zip(
            self._quick_headers, _QUICK_GROUPS, strict=True
        ):
            self._quick_grid.addWidget(header, row, 0, 1, cols)
            row += 1
            for i, key in enumerate(keys):
                self._quick_grid.addWidget(cards[key], row + i // cols, i % cols)
            row += (len(keys) + cols - 1) // cols
        for c in range(cols):
            self._quick_grid.setColumnStretch(c, 1)

    def resizeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # Spec §7: the illustration yields at narrow widths so the hero
        # text keeps its room (re-compositing when the size bucket
        # changes); spec §6: the grid reflows with width.
        self._apply_hero_pixmap()
        self._relayout_quick_grid()

    # ══════════════════════════════════════════════════════════════════════
    # Theme refresh (the M0 §6 gap list — the M2 surfaces join the
    # refresh-on-toggle path)
    # ══════════════════════════════════════════════════════════════════════
    def refresh_theme(self) -> None:
        """Re-apply theme-dependent bits: the hero illustration must be
        re-flattened against the new surface colour; the Quick Tool cards
        re-tint (all other chrome is QSS-driven and re-polishes globally)."""
        self._apply_hero_pixmap()
        for card in self._quick_cards:
            card.refresh_theme()


__all__ = ["HomeView"]
