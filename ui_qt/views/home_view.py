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

The hero is an editorial split (spec §6): an eyebrow, heading + supporting
copy + ONE ``QPushButton#HeroPrimary`` "Start Conversion" on the left,
the supplied hero illustration (decision Q5 — ``assets/hero_books_quill.png``)
filling the right ~45%. The illustration's soft alpha halo is FLATTENED
against the hero card's tinted fill (composited, never pasted onto a
different ground). V0.6.75 (the reference comparison): the visual is sized as a
FRACTION of the available width and hides only below the 500 px floor that
only the minimum-size window hits — the old fixed 200/260 px buckets with a
760 px hide cutoff left the user's ≈660 px content run text-only, which
read as "the asset isn't implemented".

COPY (spec §6 + the approved reference mockup, verified against real
capabilities — nothing invented):

  eyebrow   "WELCOME TO ELIXIR"                          (reference hero)
  heading   "Turn documents into clear, structured knowledge." (spec §6)
  support   "Books, articles and documents — summarized, organized
             and ready for you to explore."               (reference hero)
  CTA       "Start Conversion"       (spec §6 + user decision Q7)

The spec §1 brand line ("Knowledge, distilled into clarity.") lives in
the sidebar-bottom brand card since V0.6.71 — the standalone purpose
line that used to sit above the hero was retired in V0.6.75 so the hero
opens with the reference's eyebrow instead (no duplicated brand line).

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

# Hero illustration budget (V0.6.75, the reference comparison): the
# visual earns the mockup's editorial split — ~45% of the hero interior —
# scaling with the view between a compact floor and the source width
# (632 px, so it only ever scales DOWN).
_HERO_IMAGE_FRACTION = 0.45
_HERO_IMAGE_MIN_W = 180
_HERO_IMAGE_MAX_W = 430

# The budget moves in 20 px steps so a resize drag recomposites on step
# crossings only, not per pixel (the pixmap cache keys on the step).
_HERO_IMAGE_STEP = 20

# Below this CONTENT width the illustration hides (spec §7 narrow-width
# rule). V0.6.75: ONLY the 560 px minimum window's ≈330 px content band
# lands here — the old 760 px cutoff hid the visual across the user's
# actual ≈890 px Windows run (≈660 px of content after the sidebar),
# which read as "the asset isn't implemented" (the user report that
# triggered this fix).
_HERO_IMAGE_MIN_VIEW_W = 500

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
    """The M2 landing page: the Full Conversion hero + the Quick Tools
    grid (V0.6.75: the hero opens the page — the standalone purpose line
    is retired; the brand line lives in the sidebar brand card)."""

    start_requested = Signal()
    tool_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Pixmap cache key (bucket, surface) — see _apply_hero_pixmap.
        self._hero_pm_key: tuple | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 10)
        root.setSpacing(14)

        # 1 — the Full Conversion hero (the single dominant action) —
        # V0.6.75: the reference mockup opens the page with it; the old
        # standalone purpose line is retired (the spec §1 brand line
        # already lives in the sidebar-bottom brand card, V0.6.71).
        root.addWidget(self._build_hero())

        # 2 — the Quick Tools section (secondary tools only — the hero is
        # never duplicated as a tile; spec §6 / decision Q7).
        root.addLayout(self._build_quick_tools())

        root.addStretch()

    # ══════════════════════════════════════════════════════════════════════
    # The hero
    # ══════════════════════════════════════════════════════════════════════
    def _build_hero(self) -> QFrame:
        """Editorial split: text + CTA left, illustration right (spec §6).

        V0.6.75 (the reference comparison): the hero sits in its own
        TINTED container — ``QFrame#HeroCard``, the mockup's warm band one
        step above the page ground (not the plain ``QFrame#Card`` surface)
        — with the text column opening on the mockup's eyebrow, the
        reference support line, and the play-glyph pill CTA.
        """
        hero = QFrame()
        hero.setObjectName("HeroCard")
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(24)

        text_col = QVBoxLayout()
        text_col.setSpacing(10)

        # The reference hero's eyebrow (V0.6.75) — small, tracked-out,
        # sitting above the heading (QLabel#Eyebrow QSS rule).
        eyebrow = QLabel("WELCOME TO ELIXIR")
        eyebrow.setObjectName("Eyebrow")
        text_col.addWidget(eyebrow)

        heading = QLabel("Turn documents into clear, structured knowledge.")
        heading.setObjectName("Hero")
        heading.setWordWrap(True)
        text_col.addWidget(heading)

        support = QLabel(
            "Books, articles and documents — summarized, organized and ready for you to explore."
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
        self._set_cta_icon()
        self.cta_btn.clicked.connect(self.start_requested.emit)
        text_col.addWidget(self.cta_btn, 0, Qt.AlignmentFlag.AlignLeft)
        text_col.addStretch()

        lay.addLayout(text_col, 1)

        # The illustration (decision Q5) — flattened against the surface,
        # proportionally sized, hidden only below the narrow-width floor.
        self._hero_visual = QLabel()
        # V0.6.75 deadlock escape: a QLabel's content-derived minimum IS
        # its pixmap size, so without an explicit tiny minimum the visual
        # inflates the layout's minimum — the window then cannot shrink to
        # the width that would shrink the pixmap (measured: layout min 357
        # → 78 with this line; the label still takes its pixmap size when
        # the room exists). Without it the 560 px minimum window is
        # unreachable and even the 760×540 default geometry self-expands.
        self._hero_visual.setMinimumSize(1, 1)
        self._hero_visual.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lay.addWidget(self._hero_visual, 0, Qt.AlignmentFlag.AlignVCenter)
        self._apply_hero_pixmap()

        return hero

    # ── the hero CTA glyph (V0.6.75, the reference comparison) ───────────
    def _set_cta_icon(self) -> None:
        """The reference CTA's play glyph, tinted to sit on the accent
        fill — re-tinted on theme refresh (the on-accent colour flips
        between the modes)."""
        from PySide6.QtCore import QSize

        from ui_qt.components.icons import icon

        self.cta_btn.setIconSize(QSize(15, 15))
        self.cta_btn.setIcon(icon("play", theme_manager.palette.text_on_accent, 15))

    # ── the hero illustration (decision Q5) ──────────────────────────────
    def _flattened_hero_pixmap(self, max_w: int):
        """The supplied illustration scaled to ≤ ``max_w`` px wide with its
        alpha flattened onto the CURRENT hero card colour.

        The asset is 632×330 RGBA with a soft halo quarter (the M1
        inspection): pasting it straight onto a different ground would
        leave a pale rectangle. Compositing against the exact ``QFrame#
        HeroCard`` fill (``palette.bg_hero`` — MUST stay in sync with
        the QSS rule) keeps the halo invisible in BOTH themes — and is
        why ``refresh_theme`` re-runs this instead of caching one pixmap.
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
        flat.fill(QColor(theme_manager.palette.bg_hero))
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
        """(Re)composite the illustration at the width the current view
        supports, then apply the narrow-width hide rule.

        V0.6.75 (the reference comparison): the budget is PROPORTIONAL —
        ~45% of the view, clamped to 180–430 px — so the visual renders at
        every realistic width. The old fixed 200/260 px buckets plus the
        760 px hide cutoff left the user's ≈660 px content run with a
        text-only hero (the "you didn't use hero_books_quill.png"
        report). The pixmap stays cached per (budget step, card tint) so a
        resize drag only recomposites on step or theme crossings.
        """
        budget = self._hero_image_budget()
        key = (budget, theme_manager.palette.bg_hero)
        if key != self._hero_pm_key:
            if budget == 0:
                self._hero_pm_key = ("hidden",)
                self._hero_visual.setVisible(False)
                return
            pm = self._flattened_hero_pixmap(budget)
            if pm is None:
                self._hero_pm_key = ("missing",)
                self._hero_visual.setVisible(False)
                return
            self._hero_visual.setPixmap(pm)
            self._hero_pm_key = key
        self._hero_visual.setVisible(budget > 0)

    def _hero_image_budget(self) -> int:
        """Illustration width for the current view width: ~45% of the view
        clamped to [_HERO_IMAGE_MIN_W, _HERO_IMAGE_MAX_W] in 20 px steps;
        0 below the hide floor (spec §7 narrow-width rule)."""
        if self.width() < _HERO_IMAGE_MIN_VIEW_W:
            return 0
        raw = min(
            _HERO_IMAGE_MAX_W,
            max(_HERO_IMAGE_MIN_W, round(self.width() * _HERO_IMAGE_FRACTION)),
        )
        return raw // _HERO_IMAGE_STEP * _HERO_IMAGE_STEP

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
        re-flattened against the new surface colour and the CTA glyph
        re-tinted; the Quick Tool cards re-tint (all other chrome is
        QSS-driven and re-polishes globally)."""
        self._apply_hero_pixmap()
        self._set_cta_icon()
        for card in self._quick_cards:
            card.refresh_theme()


__all__ = ["HomeView"]
