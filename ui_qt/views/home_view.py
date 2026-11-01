"""M2 (UI/UX redesign): the home view — the landing page.

Spec §6 dashboard composition:
1. a concise purpose line,
2. the Full Conversion hero (the single dominant action), and
3. the Quick Tools grid of secondary tools (added by the grid commit).

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
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.theme import theme_manager

# Hero illustration budget (decision Q5: reduced size — "keep it ≤ ~260 px
# wide"; the source is 632×330, so it always scales down).
_HERO_IMAGE_MAX_W = 260

# Below this CONTENT width the illustration hides (spec §7 narrow-width
# rule): a 1280 px window − the 210 px rail ≈ 1030 px of content (shown,
# comfortably); the 560 px minimum window ≈ 330 px of content (hidden —
# the text column keeps its room).
_HERO_IMAGE_MIN_VIEW_W = 900


def _project_root() -> Path:
    """The repo root / PyInstaller bundle (the house icons.py pattern)."""
    from app_paths import bundle_dir  # V0.6.63: bundle-aware

    return bundle_dir()


class HomeView(QWidget):
    """The M2 landing page: purpose line + the Full Conversion hero
    (+ the Quick Tools grid, added by the grid commit)."""

    start_requested = Signal()
    tool_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 10)
        root.setSpacing(14)

        # 1 — the purpose line (spec §6 hierarchy; the spec §1 brand line).
        purpose = QLabel("Knowledge, distilled into clarity.")
        purpose.setObjectName("Support")
        root.addWidget(purpose)

        # 2 — the Full Conversion hero (the single dominant action).
        root.addWidget(self._build_hero())

        # 3 — the Quick Tools grid lands with the grid commit (the hero is
        # never duplicated as a tile there — spec §6 / decision Q7).
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
        pm = self._flattened_hero_pixmap(_HERO_IMAGE_MAX_W)
        if pm is None:
            self._hero_visual.setVisible(False)
            return
        self._hero_visual.setPixmap(pm)
        self._hero_visual.setVisible(self.width() >= _HERO_IMAGE_MIN_VIEW_W)

    def resizeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # Spec §7: the illustration yields at narrow widths so the hero
        # text keeps its room (the pixmap itself is only re-derived on
        # theme changes — this just shows/hides).
        if self._hero_visual.pixmap() is not None:
            self._hero_visual.setVisible(self.width() >= _HERO_IMAGE_MIN_VIEW_W)

    # ══════════════════════════════════════════════════════════════════════
    # Theme refresh (the M0 §6 gap list — the M2 surfaces join the
    # refresh-on-toggle path)
    # ══════════════════════════════════════════════════════════════════════
    def refresh_theme(self) -> None:
        """Re-apply theme-dependent bits: the hero illustration must be
        re-flattened against the new surface colour (all other chrome is
        QSS-driven and re-polishes globally)."""
        self._apply_hero_pixmap()


__all__ = ["HomeView"]
