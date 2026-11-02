"""M2 (UI/UX redesign): the home view — the landing page.

Spec §6 dashboard composition:
1. a concise purpose line,
2. the Full Conversion hero (the single dominant action), and
3. the Quick Tools grid of secondary tools, grouped Processing /
   Utilities / Audio (user decision Q1 — the Audio group is IN) with
   ``SectionLabel`` group headers.

The Quick Tools grid is fed from the EXISTING ``TOOL_CARDS`` data (the
single source of truth for keys / exact user-facing titles / one-line
descriptions; V0.6.78 additionally carries the reference's featured
"Full Conversion Wizard" ninth card — a second entry point to the same
wizard, never a duplicate of the hero's action). The emoji card icons
are swapped for the M1 Lucide glyph names (spec §7: one outline family,
no emoji). The column count reflows with the available width (spec §6
"grid reflows with available width"): V0.6.81 derives the count from the
cards' MEASURED minimum widths (the running platform's real font
metrics) — 3 columns while they fit, 2 when 3 cannot, 1 when 2 cannot —
so the grid never overflows the viewport on ANY font stack (the fixed
820/520 px thresholds were tuned on the dev font and under-estimated
what Segoe UI needs, clipping the right column in the compiled Windows
app).

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
from typing import TYPE_CHECKING

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

from ui_qt.components.dashboard_primitives import QuickToolCard
from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager
from ui_qt.views.tool_dashboard import TOOL_CARDS

# Hero illustration budget (V0.6.78, visual-fidelity pass): the reference
# renders the books/inkwell/quill still-life at effectively native scale —
# the budget is the hero INTERIOR HEIGHT fit, capped at 55% of the view
# width so narrow windows keep their text room (spec §7). The budget moves
# in 20 px steps so a resize drag recomposites on step crossings only.
_HERO_IMAGE_STEP = 20

# V0.6.81: the headline's measured display size. The reference's second
# line ("clear, structured knowledge.") spans ≈540 px in the reference
# image; at Inter SemiBold that width corresponds to 39 px (41 px — the
# V0.6.78 FONT.hero measurement from the ascender — runs the line 567 px
# wide, past the 545 px text column, re-wrapping the hard two-line break
# into three lines). The scale sweep in _scale_hero_typography anchors to
# THIS number; the QSS QLabel#Hero base stays on FONT.hero (harmless —
# the per-widget override always wins once the view is built).
_HERO_HEADLINE_PX = 39

# Below this CONTENT width the illustration hides (spec §7 narrow-width
# rule). V0.6.75: ONLY the 560 px minimum window's ≈330 px content band
# lands here — the old 760 px cutoff hid the visual across the user's
# actual ≈890 px Windows run (≈660 px of content after the sidebar),
# which read as "the asset isn't implemented" (the user report that
# triggered this fix).
_HERO_IMAGE_MIN_VIEW_W = 500

# Quick Tools (V0.6.78, visual-fidelity pass): the approved reference's
# grid — EXACTLY nine cards in the reference order, each a horizontal
# icon + title + description row with the pale circular arrow affordance;
# the ninth is the deep forest-green Full Conversion Wizard feature card
# (the spec's documented override of the old no-duplicate rule — it is a
# SECOND ENTRY POINT to the same existing wizard, never a new feature).
#
# Titles come from the existing TOOL_CARDS data (the single source of
# truth for exact user-facing names); the one-line descriptions use the
# reference's wording, each verified truthful against the existing
# feature (see the pairs below). Keys route through the EXISTING
# convert_view tool-key dispatch — no re-implementation.
_QUICK_CARDS: list[tuple[str, str, str, str, bool]] = [
    # (key, TOOL_CARDS title, reference description, Lucide glyph, featured)
    ("summarization", "", "Extract key points and get concise summaries.", "sigma", False),
    ("pdf_to_markdown", "", "Convert any document to clean Markdown format.", "file-text", False),
    ("translation", "", "Translate with high quality and natural language.", "globe", False),
    ("packets_tool", "", "Cluster notes → synthesized knowledge packets.", "layers", False),
    ("ocr_service", "", "Extract text from images and scanned documents.", "scan", False),
    ("pdf_docx_cutter", "", "Split large files into smaller chunks.", "scissors", False),
    ("image_extractor", "", "Extract images from PDF and documents.", "image", False),
    ("markdown_styler", "", "Beautify and structure your Markdown files.", "pencil", False),
    # The reference's ninth card is labelled "Full Conversion Wizard" (the
    # sidebar entry keeps the shorter "Full Conversion") — the same wizard,
    # explicitly named as one on the card.
    (
        "full_conversion",
        "Full Conversion Wizard",
        "Transform books, documents and content into clear knowledge.",
        "wand",
        True,
    ),
]

# Reflow (spec §6/P2): the reference's three equal columns at wide content
# runs, two at medium, one on narrow windows. V0.6.81: the DECISION is no
# longer made against these fixed thresholds — the column count is derived
# from the cards' measured minimum widths (see _relayout_quick_grid), so a
# column count is only chosen when the real, current font metrics say the
# columns FIT. The constants remain as the documented design intent (the
# reference's 3-column band) and as the minimum window's guaranteed floor.
_GRID_3_MIN_W = 820
_GRID_2_MIN_W = 520
_GRID_GAP = 15  # the QGridLayout's inter-column gap — kept in sync with
# the setSpacing(_GRID_GAP) call in _build_quick_tools


if TYPE_CHECKING:  # pragma: no cover — typing only
    from PySide6.QtGui import QPixmap


def _project_root() -> Path:
    """The repo root / PyInstaller bundle (the house icons.py pattern)."""
    from app_paths import bundle_dir  # V0.6.63: bundle-aware

    return bundle_dir()


def _tool_meta() -> dict[str, tuple[str, str]]:
    """key → (exact user-facing title, one-line description) from the
    existing TOOL_CARDS data — titles are never re-typed here."""
    return {key: (title, subtitle) for key, title, subtitle, _i, _c, _p in TOOL_CARDS}


class _HeroCard(QFrame):
    """The hero panel — paints the reference's soft translucent arcs and
    the understated landscape curve BEHIND the children (the QSS fills
    the warm cream ground; children — text, CTA, illustration — render
    above this decoration).

    The decoration is token-driven (sage / accent_soft at low alpha over
    the ``bg_hero`` ground) and tracks the theme; nothing is a literal.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPainter, QPainterPath

        p = theme_manager.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())

        # ── the landscape curves (bottom-right, understated) ──────────
        hill = QPainterPath(QPointF(w * 0.30, h))
        hill.quadTo(w * 0.62, h - h * 0.16, w * 0.86, h - h * 0.055)
        hill.quadTo(w * 0.95, h - h * 0.02, w, h - h * 0.06)
        hill.lineTo(w, h)
        hill.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        c1 = QColor(p.sage)
        c1.setAlpha(30)
        painter.setBrush(c1)
        painter.drawPath(hill)
        hill2 = QPainterPath(QPointF(w * 0.52, h))
        hill2.quadTo(w * 0.78, h - h * 0.10, w, h - h * 0.13)
        hill2.lineTo(w, h)
        hill2.closeSubpath()
        c2 = QColor(p.warning)
        c2.setAlpha(18)
        painter.setBrush(c2)
        painter.drawPath(hill2)

        # ── the soft translucent circles behind the books (the
        # reference's filled geometric washes, not outline arcs) ───────
        painter.setPen(Qt.PenStyle.NoPen)
        cx, cy = w * 0.72, h * 0.34
        for dia, alpha in ((h * 1.62, 34), (h * 1.14, 28), (h * 0.70, 22)):
            ac = QColor(p.sage)
            ac.setAlpha(alpha)
            painter.setBrush(ac)
            painter.drawEllipse(QRectF(cx - dia / 2, cy - dia / 2, dia, dia))
        painter.end()


class _HeroCTA(QPushButton):
    """The reference's capsule CTA — the QSS pill (play icon + label via
    the normal QPushButton affordances) plus the trailing arrow painted
    inside the pill's right inset (palette-aware, re-rendered on theme
    refresh)."""

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPainter, QPen

        p = theme_manager.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(p.text_on_accent), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        x = self.width() - 24.0
        y = self.height() / 2.0
        painter.drawLine(QPointF(x - 9, y), QPointF(x, y))
        painter.drawLine(QPointF(x - 5, y - 5), QPointF(x, y))
        painter.drawLine(QPointF(x - 5, y + 5), QPointF(x, y))
        painter.end()


class HomeView(QWidget):
    """The M2 landing page: the Full Conversion hero + the Quick Tools
    grid (V0.6.75: the hero opens the page — the standalone purpose line
    is retired; the brand line lives in the sidebar brand card)."""

    start_requested = Signal()
    tool_clicked = Signal(str)
    # V0.6.78: the reference's "View all tools →" — routes to the existing
    # full tool-dashboard page (the legacy convert view carries every
    # tool, including the audio group that left the sidebar/grid).
    view_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # V0.6.81: an EXPLICIT 1x1 minimum. QWidget's implied minimum is its
        # layout's minimumSizeHint — so while the Quick Tools grid was laid
        # out at 3 columns (a ~980 px page minimum) the enclosing
        # QScrollArea could not resize this view below ~980 px: the resize
        # events kept reporting the CLAMPED width, the reflow logic never
        # saw the narrow viewport, and the column count deadlocked at a
        # size that clipped the right column (the compiled-Windows "not
        # enough space" reports). An explicit minimum overrides the hint,
        # the scroll area always pushes the TRUE viewport width through,
        # and _relayout_quick_grid (called from resizeEvent) drops column
        # counts until the page's real minimum fits — the transient
        # sub-minimum state is corrected before the first paint. The
        # window's own usable floor is enforced at the ElixirWindow level
        # (760x440), not here.
        self.setMinimumSize(1, 1)

        # Pixmap cache key (bucket, surface) — see _apply_hero_pixmap.
        self._hero_pm_key: tuple | None = None

        # V0.6.78 (visual-fidelity pass): the reference's content insets —
        # the hero opens flush under the top bar (0 top margin; the bar's
        # bottom edge IS the hero's top edge, exactly as measured), 26 px
        # left / 30 px right of the content area.
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 0, 30, 0)
        root.setSpacing(0)
        self._hero_visual_w = 0

        # 1 — the Full Conversion hero (the single dominant action) —
        # V0.6.75: the reference mockup opens the page with it; the old
        # standalone purpose line is retired (the spec §1 brand line
        # already lives in the sidebar-bottom brand card, V0.6.71).
        self._hero = self._build_hero()
        root.addWidget(self._hero)

        # 2 — the Quick Tools section (secondary tools only — the hero is
        # never duplicated as a tile; spec §6 / decision Q7). V0.6.78: the
        # reference's ~40 px breathing room after the hero.
        root.addSpacing(40)
        root.addLayout(self._build_quick_tools())

        root.addStretch()

    # ══════════════════════════════════════════════════════════════════════
    # The hero
    # ══════════════════════════════════════════════════════════════════════
    def _build_hero(self) -> QFrame:
        """The reference's wide, shallow editorial hero (~1182×340 at the
        1536×1024 viewport, aspect ≈3.48:1): eyebrow, the two-line
        headline, the support copy, and the play+label+arrow capsule CTA
        on the left; the books/inkwell/quill still-life filling the right
        ~45% over soft translucent arcs and an understated landscape
        curve (V0.6.78, visual-fidelity pass — measured from the
        reference: eyebrow cap ~11 px at 40 px below the hero top,
        headline ascender ~30 px over two ~46 px lines, support ~20 px,
        CTA ~258×57 px capsule).
        """
        hero = _HeroCard()
        hero.setObjectName("HeroCard")
        self._hero_card = hero
        # V0.6.78: the still-life is near-full-bleed vertically (the
        # reference's quill tip reaches the hero's top band and the books
        # sit on the landscape curve) — only the TEXT column carries the
        # hero's top inset; the visual runs to the panel's bottom edge.
        # V0.6.80: the panel-level inset is minimal — the still-life runs
        # nearly the panel's full height (the reference's ink spans
        # ~92% of it); the TEXT column carries its own top inset below.
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(12, 6, 10, 0)
        lay.setSpacing(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.addSpacing(28)

        # The reference hero's eyebrow — small, tracked-out, sage.
        eyebrow = QLabel("WELCOME TO ELIXIR")
        eyebrow.setObjectName("Eyebrow")
        text_col.addWidget(eyebrow)
        text_col.addSpacing(17)

        # V0.6.81: the reference's EXACT two-line break is explicit — a
        # hard newline in the label text. The V0.6.78 wrap-cap approach
        # could never guarantee it: at 41 px Inter SemiBold the second
        # reference line ("clear, structured knowledge." ≈ 567 px) is
        # WIDER than the first line plus the next word ("Turn documents
        # into clear," ≈ 529 px), so any greedy wrap that fits line 2
        # inside a ~545 px column necessarily drags "clear," onto line 1
        # — the captured V0.6.80 render wrapped exactly that way. The
        # correction spec §Hero pins these two lines verbatim; the cap on
        # maximumWidth stays as the narrow-width guard (below ~55% scale
        # the label still wraps within its column, never clips).
        heading = QLabel("Turn documents into\nclear, structured knowledge.")
        heading.setObjectName("Hero")
        self._hero_heading = heading
        heading.setWordWrap(True)
        heading.setMaximumWidth(545)
        text_col.addWidget(heading)
        text_col.addSpacing(12)

        support = QLabel(
            "Books, articles and documents — summarized, organized and ready for you to explore."
        )
        support.setObjectName("Support")
        self._hero_support = support
        support.setWordWrap(True)
        support.setMaximumWidth(520)
        text_col.addWidget(support)
        text_col.addSpacing(20)

        # ONE clear primary action (spec §6). Decision Q7: the header
        # "✨ Process Wizard" button is gone; the hero owns the entry and
        # both landed in the same milestone so the primary entry never
        # gaps. The tooltip is the removed header button's exact copy.
        self.cta_btn = _HeroCTA("Start Conversion")
        self.cta_btn.setObjectName("HeroPrimary")
        self.cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta_btn.setToolTip("Open the guided step-by-step conversion wizard")
        self._set_cta_icon()
        self.cta_btn.clicked.connect(self.start_requested.emit)
        text_col.addWidget(self.cta_btn, 0, Qt.AlignmentFlag.AlignLeft)
        text_col.addSpacing(24)
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
        self._hero_visual.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._hero_visual, 0, Qt.AlignmentFlag.AlignVCenter)
        self._apply_hero_pixmap()

        return hero

    # ── the hero CTA glyph (V0.6.78, the reference comparison) ───────────
    def _set_cta_icon(self) -> None:
        """The reference CTA's play glyph, tinted to sit on the accent
        fill — re-tinted on theme refresh (the on-accent colour flips
        between the modes)."""
        from PySide6.QtCore import QSize

        from ui_qt.components.icons import icon

        self.cta_btn.setIconSize(QSize(16, 16))
        self.cta_btn.setIcon(icon("play", theme_manager.palette.text_on_accent, 16))

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
        # V0.6.78: the shipped asset carries wide transparent margins
        # (ink bbox ≈ x[60,575] y[17,329] on the 632×330 canvas) — the
        # reference's still-life FILLS its band, so crop to the ink (plus
        # a 6 px cushion) before scaling; otherwise the visible books
        # render ~25% smaller than the reference at the same box.
        crop = self._asset_ink_crop(src)
        w = min(max_w, crop.width())
        h = max(1, round(crop.height() * w / crop.width()))
        flat = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        flat.fill(QColor(theme_manager.palette.bg_hero))
        painter = QPainter(flat)
        painter.drawPixmap(
            0,
            0,
            crop.scaled(
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        painter.end()
        return QPixmap.fromImage(flat)

    @staticmethod
    def _asset_ink_crop(src: QPixmap):
        """The asset cropped to its alpha ink (+6 px cushion) — cached on
        the class (the PNG is static; the scan is a one-off)."""
        cached = getattr(HomeView, "_ink_crop", None)
        if cached is not None and not cached.isNull():
            return cached
        img = src.toImage()
        x0, y0, x1, y1 = img.width(), img.height(), 0, 0
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixel(x, y) >> 24 > 12:
                    x0 = min(x0, x)
                    x1 = max(x1, x)
                    y0 = min(y0, y)
                    y1 = max(y1, y)
        if x1 <= x0 or y1 <= y0:
            HomeView._ink_crop = src
            return src
        pad = 6
        x0 = max(0, x0 - pad)
        y0 = max(0, y0 - pad)
        x1 = min(img.width() - 1, x1 + pad)
        y1 = min(img.height() - 1, y1 + pad)
        HomeView._ink_crop = src.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        return HomeView._ink_crop

    def _apply_hero_pixmap(self) -> None:
        """(Re)composite the illustration at the size the current hero
        supports, then apply the narrow-width hide rule.

        V0.6.78 (visual-fidelity pass): the reference renders the
        books/inkwell/quill at effectively NATIVE scale filling the
        hero's height — the budget is now HEIGHT-driven (the hero's
        interior height, capped at ~55% of the interior width so narrow
        windows keep their text room), replacing V0.6.75's width
        fraction. The pixmap stays cached per (budget step, card tint).
        """
        budget = self._hero_image_budget()
        key = (budget, theme_manager.palette.bg_hero)
        if key != self._hero_pm_key:
            if budget == 0:
                self._hero_pm_key = ("hidden",)
                self._hero_visual.setVisible(False)
                self._hero_visual_w = 0
                return
            pm = self._flattened_hero_pixmap(budget)
            if pm is None:
                self._hero_pm_key = ("missing",)
                self._hero_visual.setVisible(False)
                self._hero_visual_w = 0
                return
            self._hero_visual.setPixmap(pm)
            self._hero_pm_key = key
            self._hero_visual_w = pm.width()
        self._hero_visual.setVisible(budget > 0)

    def _hero_image_budget(self) -> int:
        """Illustration width for the current hero size: the interior
        HEIGHT fit (the reference's native-scale still-life), capped at
        55% of the interior width; 0 below the hide floor (spec §7
        narrow-width rule)."""
        if self.width() < _HERO_IMAGE_MIN_VIEW_W:
            return 0
        # The height target is the reference-proportioned hero height
        # (~29% of the content width, clamped 230–340) — NOT the card's
        # live height, which the pixmap itself would inflate (a feedback
        # loop: taller card → bigger budget → taller pixmap → …).
        target_h = max(230, min(340, round(self.width() * 0.29)))
        inner_h = target_h - 8
        if inner_h < 110:
            inner_h = 222  # pre-first-layout fallback (230 - 8)
        by_h = round(inner_h * 504 / 318)  # the ink-crop's aspect
        by_w = round(self.width() * 0.55)
        raw = max(120, min(by_h, by_w))
        return raw // _HERO_IMAGE_STEP * _HERO_IMAGE_STEP

    # ══════════════════════════════════════════════════════════════════════
    # The Quick Tools grid (spec §6: compact, consistent, reflowing)
    # ══════════════════════════════════════════════════════════════════════
    def _build_quick_tools(self) -> QVBoxLayout:
        """The reference's Quick Tools section: ONE heading row — the sage
        zap glyph + "Quick Tools" + the "View all tools →" action at the
        far right — over the three-column card grid (V0.6.78: the old
        per-group PROCESSING/UTILITIES/AUDIO section headers are retired;
        the reference inserts nothing between the heading and the cards).
        """
        section = QVBoxLayout()
        section.setSpacing(0)

        head_row = QHBoxLayout()
        head_row.setContentsMargins(3, 0, 3, 0)
        head_row.setSpacing(10)
        p = theme_manager.palette
        zap = QLabel()
        zap.setPixmap(icon("zap", p.sage, 20).pixmap(20, 20))
        head_row.addWidget(zap, 0, Qt.AlignmentFlag.AlignVCenter)
        head = QLabel("Quick Tools")
        head.setObjectName("SectionHead")
        head_row.addWidget(head)
        head_row.addStretch(1)
        self._view_all_btn = QPushButton("View all tools  →")
        self._view_all_btn.setObjectName("ViewAllLink")
        self._view_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_all_btn.setToolTip("Open the full tools page (every tool, including audio)")
        self._view_all_btn.clicked.connect(self.view_all_requested.emit)
        head_row.addWidget(self._view_all_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        section.addLayout(head_row)
        section.addSpacing(22)

        self._quick_cards: list[QuickToolCard] = []
        self._quick_grid = QGridLayout()
        self._quick_grid.setSpacing(_GRID_GAP)
        self._grid_cols = 0  # forces the first _relayout to lay everything out
        meta = _tool_meta()
        for key, title, desc, glyph, featured in _QUICK_CARDS:
            card_title = title or meta.get(key, (key, ""))[0]
            card = QuickToolCard(
                key, card_title, description=desc, icon_name=glyph, featured=featured
            )
            card.clicked.connect(self.tool_clicked.emit)
            self._quick_cards.append(card)
        section.addLayout(self._quick_grid)
        self._relayout_quick_grid()
        return section

    def _relayout_quick_grid(self) -> None:
        """(Re)place the cards into the grid at the column count the current
        width ACTUALLY supports — the reference's three equal columns, two
        at medium widths, one on narrow windows. Cards are persistent
        widgets — they are re-added, never rebuilt (click routing + focus
        live on the card, so a reflow loses nothing).

        V0.6.81 (the Windows "not enough space" fix): the count is decided
        by MEASUREMENT, not by fixed pixel thresholds. Candidates are tried
        from the reference's 3 down to 1, and a count is only kept when the
        page's own measured minimum — every card title, the heading row and
        the hero at the REAL metrics of the running font stack — fits the
        width the scroll viewport is actually offering. The old fixed
        thresholds (820/520) were tuned on the dev box's Inter and
        UNDER-estimated what other stacks need: on a Windows machine
        (Segoe UI ~10% wider when the bundled Inter fails to register) a
        ~530 px content run picked 2 columns needing ~620 px, the home
        view's minimum width exceeded the scroll viewport, and the right
        column + the "View all tools" action clipped out of sight — while
        the dev-side preview, rendering the same geometry with narrower
        glyphs, looked fine. Measurement cannot drift from any font stack:
        whatever the metrics, the count only drops when the REAL minimum
        says the columns cannot fit.

        The width the decision is made against is ``self.width()`` — the
        TRUE space on offer, guaranteed by the explicit 1x1 minimum set in
        ``__init__`` (see the note there: without it the scroll area clamps
        this view at its own layout minimum and the reflow never sees a
        narrower viewport).

        Qt quirk this lives with: re-parenting layout items does not, by
        itself, refresh the PAGE-level ``layout().minimumSize()`` — its
        cache still describes the previous column count until a LayoutRequest
        is processed. ``_lay_grid_columns`` therefore calls
        ``self.layout().activate()`` after re-adding the cards, which
        recomputes the page minimum SYNCHRONOUSLY — the check below always
        runs against live numbers, in the same event, with no deferred
        settling."""
        width = max(self.width(), 1)
        for cols in (3, 2, 1):
            if cols != self._grid_cols:
                self._lay_grid_columns(cols)
            if self.layout().minimumSize().width() <= width:
                return
        # Even one column overflows (a font stack wider than any the
        # window minimum was sized for) — the 1-column layout laid out
        # above is the least-bad result, exactly as before.

    def _lay_grid_columns(self, cols: int) -> None:
        """Move the persistent cards into a fresh ``cols``-column grid
        (the widget children survive a reflow — only the layout items are
        re-parented). Finishes with ``layout().activate()`` so the page
        minimum the caller checks reflects THIS column count immediately
        (Qt's page-level minimum cache otherwise still describes the
        previous count until a posted LayoutRequest runs)."""
        self._grid_cols = cols
        while self._quick_grid.count():
            self._quick_grid.takeAt(0)  # items only — the widgets survive
        for i, card in enumerate(self._quick_cards):
            self._quick_grid.addWidget(card, i // cols, i % cols)
        for c in range(cols):
            self._quick_grid.setColumnStretch(c, 1)
        rows = (len(self._quick_cards) + cols - 1) // cols
        for r in range(self._quick_grid.rowCount()):
            # Retired rows (a reflow from more columns to fewer leaves
            # empty rows behind — QGridLayout cannot delete them) MUST
            # drop their minimums again, or the stale 120 px floors
            # inflate the page's minimum ~240 px past the scroll
            # viewport (the V0.6.80 scrollbar catch).
            self._quick_grid.setRowMinimumHeight(r, 120 if r < rows else 0)
            self._quick_grid.setRowStretch(r, 0)
        self.layout().activate()  # synchronous minimum refresh — see above

    def resizeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # V0.6.78: the hero keeps the reference's wide/shallow proportion
        # (~29% of the content width — 340 px at the 1180 px reference
        # content run), clamped 230–340 so narrow windows still breathe.
        hero_h = max(240, min(340, round(self.width() * 0.29)))
        if getattr(self, "_hero", None) is not None and getattr(self, "_hero_h", None) != hero_h:
            self._hero_h = hero_h
            # V0.6.81: MINIMUM, not FIXED. The fixed height clipped the
            # hero's text column on wider/taller font stacks (Windows Segoe
            # UI needs ~15% more vertical room than the dev font at the
            # same px size — the CTA / the heading's last line were cut at
            # the 240 px floor). A wordWrap label's height-for-width
            # minimum now grows the hero exactly as much as the real text
            # needs and NO more: at the reference viewport (Inter) the
            # layout minimum stays ≈320 px < 340, so the V0.6.80 guarantee
            # (the full dashboard fits with NO scrollbar) is preserved,
            # while a taller font stack stretches the hero instead of
            # clipping it.
            self._hero.setMinimumHeight(hero_h)
        # V0.6.79 (spec P2): at narrow content runs the hero's typography
        # scales DOWN with the width (never below 55% — the hierarchy is
        # preserved; a 41 px headline cannot fit a 217 px column, which
        # clipped "documents" at the 560 px minimum window).
        self._scale_hero_typography()
        # Spec §7: the illustration yields at narrow widths so the hero
        # text keeps its room (re-compositing when the size bucket
        # changes); spec §6: the grid reflows with width.
        self._apply_hero_pixmap()
        self._relayout_quick_grid()

    def _scale_hero_typography(self) -> None:
        """Scale the hero's display type with the available width (the
        reference's 41/22 px at the 1180 px content run, down to 55% at
        the narrow minimum window) — and re-cap the wrap widths so the
        words always fit their column."""
        from ui_qt.theme import FONT

        if getattr(self, "_hero_heading", None) is None:
            return
        scale = max(0.55, min(1.0, self.width() / 1180))
        # _HERO_HEADLINE_PX (V0.6.81): the measured fit for the reference's
        # exact two-line break — see the constant's note.
        hero_px = max(22, round(_HERO_HEADLINE_PX * scale))
        support_px = max(13, round(FONT.body_lg * scale))
        # V0.6.81: the wrap caps are re-applied on EVERY call — they used
        # to sit below the font-size early-return, so while the scale was
        # pegged at the 0.55 floor (every width < ~650 px) a column that
        # had narrowed kept its stale, too-wide cap from the last resize
        # above the floor. The cap is a maximum, so the stale value never
        # clipped text, but it defeated the intended 2-line wrap tuning.
        col = max(160, self.width() - 90)
        self._hero_heading.setMaximumWidth(max(200, min(round(545 * scale), col)))
        self._hero_support.setMaximumWidth(max(190, min(round(520 * scale), col)))
        if getattr(self, "_hero_scale", None) == (hero_px, support_px):
            return
        self._hero_scale = (hero_px, support_px)
        self._hero_heading.setStyleSheet(
            f"font-size: {hero_px}px; font-weight: 600;"
            f"color: {theme_manager.palette.text_primary}; background: transparent;"
        )
        self._hero_support.setStyleSheet(
            f"font-size: {support_px}px; color: {theme_manager.palette.text_secondary};"
            f" background: transparent;"
        )

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
