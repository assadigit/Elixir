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

# Reflow (spec §6/P2 + Round-3 §4.1 + Round-4 §2.3): the reference's
# three equal columns at wide content runs, two at medium, one on narrow
# windows. V0.6.84 (Round-4 §2.3) — the decision is FLOOR-driven:
#   * 3 columns while the grid can give every card the compact
#     readability floor (_TOOL_CARD_FLOOR_W — wrapped 2-line titles,
#     never a clip) — "Use the actual available content width to
#     determine column count"; the Round-3 single-line comfort GATE is
#     retired (it needed ≈860 px of grid, which the user's real ~790 px
#     grid can never offer — the audit's "two columns; only four cards
#     visible"),
#   * 2 columns down to two floor-width cards,
#   * 1 column only when even two floor-width cards cannot fit.
# The V0.6.81 measured page-minimum verification still runs beneath it
# (a count is only KEPT when the page's real minimum fits the viewport
# the scroll area is offering).
_GRID_3_MIN_W = 820
_GRID_2_MIN_W = 520
# V0.6.82 (Round-2 correction): the reference's inter-card gap measured
# 12-13 px (row bands [510..634]/[646..770]/[781..912]).
# V0.6.84 (Round-4 §2.2): 12 — the spec's "approximately 10–12 px
# horizontal and vertical gaps" band, mid-value; kept in sync with the
# setSpacing call in _build_quick_tools.
_GRID_GAP = 12

# ── the Round-4 card density band (V0.6.84, spec §2.2) ────────────────────
# The card height is BODY-driven like the hero: ~0.135 of the scroll
# viewport (the reference proportion — cards ≈0.13 of its body), floored
# at 84 (the spec's "approximately 80–90 logical px" compact height — the
# user's ~628 px body produces exactly that) and ceiled at 122 (the
# V0.6.82 reference render at the 1536-wide canvas).
_CARD_H_MIN = 84
_CARD_H_MAX = 122
_CARD_BODY_RATIO = 0.135

# ── the Round-3 hero rhythm (V0.6.83, spec §6; retuned V0.6.84) ────────
# The hero's target height is BODY-driven: ~0.325 of the scroll viewport's
# height, clamped to a floor/ceiling band. V0.6.84 (Round-4 §2.2): the
# floor drops 240 → 210 — at the user's ~582 px body the 240 floor had the
# hero consuming 45% of the viewport (the reference composes its hero at
# ~38%), pushing the third grid row past the fold. At 210 the hero lands
# ≈36% and the full 3×3 grid + heading fit the viewport with ~15 px to
# spare. The 336 ceiling stays (the reference rhythm at wide canvases).
_HERO_BODY_RATIO = 0.325
_HERO_MIN_H = 210
_HERO_MAX_H = 336
# The reference text-column rhythm the hero's typography/spacing scales
# from (the V0.6.82 ink-calibrated values: 33 top, 16/12/36/18 gaps, the
# 39 px two-line headline, 18 px two-line support, the 57 px capsule CTA)
# — at scale 1.0 the column measures ≈336 px, the reference hero's height.
_HERO_RHYTHM_BASE_H = 336


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
        # V0.6.84 (Round-4 §7): the washes step back (alpha 34/28/22 →
        # 24/18/14) so the books/quill/inkwell still-life is the focal
        # point — the spec's "Refine the background shapes if they
        # compete with the artwork. The books and quill should be the
        # focal point, not the decorative circles."
        painter.setPen(Qt.PenStyle.NoPen)
        cx, cy = w * 0.72, h * 0.34
        for dia, alpha in ((h * 1.62, 24), (h * 1.14, 18), (h * 0.70, 14)):
            ac = QColor(p.sage)
            ac.setAlpha(alpha)
            painter.setBrush(ac)
            painter.drawEllipse(QRectF(cx - dia / 2, cy - dia / 2, dia, dia))
        painter.end()


class _HeroCTA(QPushButton):
    """The reference's capsule CTA — a QPainter-drawn pill (V0.6.82) plus
    the play icon + label via the normal QPushButton affordances and the
    trailing arrow painted inside the pill's right inset (palette-aware,
    re-rendered on theme refresh).

    V0.6.82 (Round-2 correction): the capsule is painted DIRECTLY, not by
    the app-level QSS. Three independent renderers were measured painting
    ``QPushButton#HeroPrimary { background; border: 1px; border-radius }``
    as a SQUARE when the rule lives on the QApplication stylesheet — the
    offscreen/raster stack here (the dev preview that kept disagreeing
    with the field), and the V0.6.80 Windows build (the square CTA in the
    user's ``now2.png``). Widget-level stylesheets and QFrame rules round
    fine on the same stacks, so the engine's button path is the unstable
    one. Painting the rounded rect here is deterministic on EVERY
    platform and keeps the QSS rule for typography/padding only.
    """

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPainter, QPen

        p = theme_manager.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # ── the capsule fill (hover/pressed/disabled track the palette) ──
        if not self.isEnabled():
            fill = QColor(p.bg_input)
        elif self.isDown():
            fill = QColor(p.accent_pressed)
        elif self.underMouse():
            fill = QColor(p.accent_hover)
        else:
            fill = QColor(p.accent)
        radius = self.height() / 2.0
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(QPen(fill, 1))  # the 1px self-coloured seam
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()

        # label + icon over the transparent QSS background
        super().paintEvent(event)

        # ── the trailing arrow ──────────────────────────────────────────
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(p.text_on_accent if self.isEnabled() else p.text_muted), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        # V0.6.82: inset 26 — the reference's arrow sits ~26 px from the
        # pill's right edge (measured [557..561] inside [335..587]) at
        # the 48 px QSS padding.
        # V0.6.84 (Round-4, the "Conversion➜" collision): the inset and
        # the glyph scale WITH the hero (set by _scale_hero_typography
        # alongside the padding) so the arrow keeps its measured relation
        # to the label at every size — at the user's ~0.72 scale the old
        # fixed 26 px inset landed the arrow flush against the label.
        x = self.width() - float(getattr(self, "_arrow_inset", 26.0))
        ln = float(getattr(self, "_arrow_len", 9.0))
        hd = float(getattr(self, "_arrow_head", 5.0))
        y = self.height() / 2.0
        painter.drawLine(QPointF(x - ln, y), QPointF(x, y))
        painter.drawLine(QPointF(x - hd, y - hd), QPointF(x, y))
        painter.drawLine(QPointF(x - hd, y + hd), QPointF(x, y))
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
        # left / 30 px right of the content area. V0.6.82 (Round-2
        # correction, ink-calibrated): the reference's hero spans
        # x[308..1487] against a rail edge at 285 and shell edge at 1516 —
        # margins 22/29 place the hero cream exactly there (was 26/30 →
        # [314..1483]).
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 0, 29, 0)
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
        # reference's ~40 px breathing room after the hero. V0.6.82:
        # measured 43 px (hero bottom 430 → heading ink 473).
        # V0.6.83 (Round-3 §6): 28.
        # V0.6.84 (Round-4 §8, layout polish): 18 — the compact rhythm's
        # band; with the 210 hero floor the whole page (hero + heading +
        # the 3×3 grid) fits the user's ~582 px viewport with no scrollbar.
        root.addSpacing(18)
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
        # V0.6.82 (Round-2 correction, ink-calibrated): the reference's
        # text column starts at hero+27 (heading/CTA ink at x=335 with the
        # hero cream starting at 308 — was +15 with the old 12 px margin)
        # and the artwork runs FULL-BLEED to the hero's right edge (the
        # reference's art reaches x=1486 with the cream ending 1487 —
        # right margin 10 → 0).
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(26, 6, 0, 0)
        lay.setSpacing(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        # V0.6.82: measured rhythm (ink positions vs the reference:
        # eyebrow 132/134, heading 171/171, support 277/277, CTA
        # 352/352) — the column opens 33 px below the hero top and the
        # pre-CTA air is 36.
        # V0.6.83 (Round-3 §6): the fixed rhythm spacers become SCALEABLE
        # QSpacerItems — _scale_hero_typography retunes them (× the hero
        # scale s) so the text column tracks the body-driven hero target
        # instead of locking the card at the 336 px reference height.
        self._hero_spacers: list[tuple[object, int]] = []

        def _rhythm(base: int) -> None:
            """Append one scalable rhythm spacer (base px at scale 1.0)."""
            from PySide6.QtWidgets import QSizePolicy, QSpacerItem

            item = QSpacerItem(0, base, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._hero_spacers.append((item, base))
            text_col.addItem(item)

        _rhythm(33)

        # The reference hero's eyebrow — small, tracked-out, sage.
        eyebrow = QLabel("WELCOME TO ELIXIR")
        eyebrow.setObjectName("Eyebrow")
        self._hero_eyebrow = eyebrow
        text_col.addWidget(eyebrow)
        _rhythm(16)

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
        _rhythm(12)

        # V0.6.82 (Round-2 correction): the reference's EXACT two-line
        # support break is pinned the same way the headline is — greedy
        # wrap put "and" on line 1 ("…organized and" / "ready for you to
        # explore."), the correction spec §Hero pins
        #   "Books, articles and documents — summarized, organized"
        #   "and ready for you to explore."
        # (reference line inks: 495 px and 265 px). The maximumWidth cap
        # below stays as the narrow-width guard.
        support = QLabel(
            "Books, articles and documents — summarized, organized\nand ready for you to explore."
        )
        support.setObjectName("Support")
        self._hero_support = support
        support.setWordWrap(True)
        support.setMaximumWidth(520)
        text_col.addWidget(support)
        _rhythm(36)

        # ONE clear primary action (spec §6). Decision Q7: the header
        # "✨ Process Wizard" button is gone; the hero owns the entry and
        # both landed in the same milestone so the primary entry never
        # gaps. The tooltip is the removed header button's exact copy.
        # V0.6.83 (Round-3 §6): the CTA keeps a 44 px touch floor while
        # _scale_hero_typography scales its QSS padding with the hero.
        self.cta_btn = _HeroCTA("Start Conversion")
        self.cta_btn.setObjectName("HeroPrimary")
        self.cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta_btn.setToolTip("Open the guided step-by-step conversion wizard")
        self.cta_btn.setMinimumHeight(44)
        self._set_cta_icon()
        self.cta_btn.clicked.connect(self.start_requested.emit)
        text_col.addWidget(self.cta_btn, 0, Qt.AlignmentFlag.AlignLeft)
        _rhythm(18)
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

    # ── the hero illustration (decision Q5 + Round-3 §5) ───────────────────
    def _scaled_hero_pixmap(self, max_w: int):
        """The still-life as a TRUE transparent RGBA pixmap, scaled to ≤
        ``max_w`` px wide (V0.6.83, Round-3 §5).

        The asset is 632×330 RGBA; its background pixels are genuinely
        transparent (alpha 0 with feathered edges — the §5.2 validation),
        so the books/quill/inkwell composite DIRECTLY over the hero card's
        painted surface (cream ground + sage washes + landscape curve) —
        the layered composition the spec §5.3 requires. The V0.6.78–82
        "flatten onto ``bg_hero``" step is RETIRED: it baked an opaque
        rectangle that occluded the card's painted decoration — the exact
        "visible rectangular boundary" the Round-3 audit flags. The QLabel
        paints transparently (QSS ``QLabel`` base rule), so the asset's
        alpha halo now blends over BOTH themes' decorated hero surface.
        """
        from PySide6.QtGui import QPixmap

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
        w = max_w
        h = max(1, round(crop.height() * w / crop.width()))
        return crop.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

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
        """(Re)apply the illustration at the size the current hero
        supports, then apply the narrow-width hide rule.

        V0.6.83 (Round-3 §5): the pixmap is now TRANSPARENT — it carries no
        baked surface, so the cache key is the budget alone (a theme toggle
        no longer recomposites anything; refresh_theme still calls through
        here, a no-op when the key is unchanged).
        """
        budget = self._hero_image_budget()
        key = (budget,)
        if key != self._hero_pm_key:
            if budget == 0:
                self._hero_pm_key = ("hidden",)
                self._hero_visual.setVisible(False)
                self._hero_visual_w = 0
                return
            pm = self._scaled_hero_pixmap(budget)
            if pm is None:
                self._hero_pm_key = ("missing",)
                self._hero_visual.setVisible(False)
                self._hero_visual_w = 0
                return
            self._hero_visual.setPixmap(pm)
            self._hero_pm_key = key
            self._hero_visual_w = pm.width()
        self._hero_visual.setVisible(budget > 0)

    # ── the Round-3 hero geometry (V0.6.83, spec §2/§6) ───────────────────
    def _body_height(self) -> int:
        """The TRUE available height for the dashboard: the enclosing
        scroll area's VIEWPORT height (not ``self.height()`` — once the
        content overflows, the view grows past the viewport and would
        feed the hero rule a number the user never sees)."""
        from PySide6.QtWidgets import QScrollArea

        p = self.parent()
        while p is not None:
            if isinstance(p, QScrollArea):
                h = p.viewport().height()
                if h > 0:
                    return h
            p = p.parent()
        return max(1, self.height() or 640)

    def _hero_target_h(self) -> int:
        """The Round-3 hero height: ~0.325 of the available body height,
        clamped [_HERO_MIN_H, _HERO_MAX_H]. Spec §6: "approximately
        220–250 px, adapting gently to available space" — at the 1440×900
        composition (764 px of body) this lands ≈248; the reference window
        (888 px of body) gets ≈289 — the audit's "reduce its relative
        height" vs the reference's ~0.38 share."""
        return max(_HERO_MIN_H, min(_HERO_MAX_H, round(self._body_height() * _HERO_BODY_RATIO)))

    def _hero_text_need_w(self) -> int:
        """The minimum text column the PINNED hero copy needs at the current
        scale (V0.6.83, Round-3 §5.3/§6): the measured width of the heading's
        wider hard line and the support's first line on the RUNNING font
        metrics (the labels' own styled fonts — weight included), plus air.

        The art budget respects this FIRST — the still-life yields before
        the text column ever wraps the pinned two-line breaks (the V0.6.81
        hard-newline guarantee at every supported size)."""
        need = 320
        heading = getattr(self, "_hero_heading", None)
        if heading is not None:
            fm = heading.fontMetrics()
            need = max(
                need,
                fm.horizontalAdvance("clear, structured knowledge."),
                fm.horizontalAdvance("Turn documents into"),
            )
        support = getattr(self, "_hero_support", None)
        if support is not None:
            need = max(
                need,
                support.fontMetrics().horizontalAdvance(
                    "Books, articles and documents — summarized, organized"
                ),
            )
        return need + 30

    def _hero_image_budget(self) -> int:
        """Illustration width for the current hero size: the Round-3 hero
        target's HEIGHT fit (the reference's still-life spans ~92% of the
        panel height, aspect 504/318), capped at 55% of the view width and
        — V0.6.83 — by the text column's measured need (the art yields
        before the pinned copy wraps); 0 below the hide floor (spec §7
        narrow-width rule)."""
        if self.width() < _HERO_IMAGE_MIN_VIEW_W:
            return 0
        target_h = self._hero_target_h()
        by_h = round((target_h + 2) * 504 / 318)  # the ink-crop's aspect
        by_w = round(self.width() * 0.55)
        card_w = max(0, self.width() - 22 - 29)
        by_text = card_w - 26 - 18 - self._hero_text_need_w()
        raw = max(120, min(by_h, by_w, by_text))
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
        # V0.6.82 (Round-2 correction): the reference's heading→grid air —
        # heading row bottom ≈499, first card top 510 → 11 px (was 22).
        # V0.6.84 (Round-4 §8): 6 — the compact band (every page-level gap
        # re-measured for the density pass).
        section.addSpacing(6)

        self._quick_cards: list[QuickToolCard] = []
        self._quick_grid = QGridLayout()
        # V0.6.84 (Round-4 §2.2): 12 px horizontal / 11 px vertical — both
        # inside the spec's "approximately 10–12 px" band; the vertical
        # pinch buys the third row back at the compact body.
        self._quick_grid.setHorizontalSpacing(12)
        self._quick_grid.setVerticalSpacing(11)
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

    def _card_comfort_width(self) -> int:
        """The measured SINGLE-LINE comfort width: the widest card title
        on the RUNNING font stack (each card's OWN styled label metrics
        — V0.6.81's font-stack-proof measurement) plus the card chrome
        (_TOOL_CARD_CHROME_W).

        V0.6.84 (Round-4 §2.3): informational only — the three-column
        decision no longer GATES on it (the compact floor does); the
        number stays the documented ceiling at which every title renders
        single-line, used by the characterization tests.
        """
        from ui_qt.components.dashboard_primitives import _TOOL_CARD_CHROME_W as chrome

        widest = 0
        for card in getattr(self, "_quick_cards", []) or []:
            label = getattr(card, "_title_label", None)
            if label is None:
                continue
            fm = label.fontMetrics()
            widest = max(widest, fm.horizontalAdvance(label.text()))
        return widest + chrome

    # ── the Round-4 card density band (V0.6.84, spec §2.2) ─────────────
    def _card_target_h(self) -> int:
        """The compact card height: ~0.135 of the available body height,
        clamped [_CARD_H_MIN, _CARD_H_MAX] — 84 at the user's ~628 px body
        (the spec's 80–90 band), 122 at the 1536-wide reference canvas
        (the V0.6.82 render)."""
        return max(_CARD_H_MIN, min(_CARD_H_MAX, round(self._body_height() * _CARD_BODY_RATIO)))

    def _apply_grid_density(self) -> None:
        """Apply the density band to every card + grid row minimum (the
        cards keep their vertical-centred text block; the extra height
        reads as air, exactly like the reference's roomy cards).

        The card TYPOGRAPHY tracks the same band — 13/11 px at the
        compact floor (single-line titles in the ~149 px text column a
        three-column row offers at the user's window), 17/13 px at the
        reference ceiling (the V0.6.82 ink-calibrated render). A fixed
        14 px title wrapped to two lines at the compact width and pushed
        the cards past the spec's 80–90 px height band; a fixed 13 px
        would lose the reference's character at the wide canvas — the
        band keeps both."""
        h = self._card_target_h()
        if getattr(self, "_card_h", None) == h:
            return
        self._card_h = h
        s = (h - _CARD_H_MIN) / (_CARD_H_MAX - _CARD_H_MIN)
        # V0.6.84.1: the desc band drops its floor 11 → 10 — with the
        # tightened chrome (97 px) the featured card's two-line break
        # needs 160 px and gets 162 at the field window, but only while
        # the desc stays at/below the compact floor's metrics.
        title_px = round(13 + 4 * s, 1)
        desc_px = round(10 + 3 * s, 1)
        for card in getattr(self, "_quick_cards", []) or []:
            card.setMinimumHeight(h)
            card.set_density(title_px, desc_px)
        rows = (len(self._quick_cards) + max(1, getattr(self, "_grid_cols", 1)) - 1) // max(
            1, getattr(self, "_grid_cols", 1)
        )
        for r in range(self._quick_grid.rowCount()):
            self._quick_grid.setRowMinimumHeight(r, h if r < rows else 0)

    def _relayout_quick_grid(self) -> None:
        """(Re)place the cards into the grid at the column count the current
        width ACTUALLY supports — the reference's three equal columns, two
        at medium widths, one on narrow windows. Cards are persistent
        widgets — they are re-added, never rebuilt (click routing + focus
        live on the card, so a reflow loses nothing).

        V0.6.84 (Round-4 §2.3): the decision is FLOOR-driven —

        * 3 while the grid gives every card the compact readability floor
          (_TOOL_CARD_FLOOR_W — 2-line wrapped titles, never a clip),
        * 2 while two floor-width cards fit,
        * 1 only when even two cannot.

        The Round-3 single-line comfort GATE is retired: it required
        ≈3×(title+chrome)+2×gap ≈ 860 px of grid, which the user's real
        ~790 px grid can never offer — exactly the audit's "two columns;
        only four cards visible". The spec's "Do not hardcode a two-column
        grid. Do not allow one card per row at ordinary desktop
        dimensions" is now structurally guaranteed: at the app's own
        1100×720 minimum window the grid width is ≈807 px ≥ 3×240+2×12.

        V0.6.81 (the Windows "not enough space" fix) stays as the safety
        net beneath the floors: a candidate count is only KEPT when the
        page's own measured minimum — every card title, the heading row
        and the hero at the REAL metrics of the running font stack — fits
        the width the scroll viewport is actually offering. Measurement
        cannot drift from any font stack.

        The width the decision is made against is ``self.width()`` — the
        TRUE space on offer, guaranteed by the explicit 1x1 minimum set in
        ``__init__``.

        Qt quirk this lives with: re-parenting layout items does not, by
        itself, refresh the PAGE-level ``layout().minimumSize()`` — its
        cache still describes the previous column count until a LayoutRequest
        is processed. ``_lay_grid_columns`` therefore calls
        ``self.layout().activate()`` after re-adding the cards, which
        recomputes the page minimum SYNCHRONOUSLY — the check below always
        runs against live numbers, in the same event, with no deferred
        settling."""
        from ui_qt.components.dashboard_primitives import _TOOL_CARD_FLOOR_W as floor

        width = max(self.width(), 1)
        grid_w = max(0, width - 22 - 29)  # the page's own content margins
        if grid_w >= 3 * floor + 2 * _GRID_GAP:
            cand = 3
        elif grid_w >= 2 * floor + _GRID_GAP:
            cand = 2
        else:
            cand = 1
        for cols in (3, 2, 1):
            if cols > cand:
                continue
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
        # V0.6.82 (Round-2 correction, the resize-sweep catch): retired
        # columns keep their stretch factors after a reflow to fewer
        # columns (takeAt removes items, never column metadata) — an empty
        # stretch-1 column then eats up to a third of the grid, so the
        # 2-column layout rendered two squeezed cards beside a dead
        # column and the 1-column layout never filled the viewport. Every
        # column slot up to the largest count ever laid out is reset
        # explicitly; only the ACTIVE columns carry stretch.
        for c in range(max(cols, getattr(self, "_grid_cols_max", cols))):
            self._quick_grid.setColumnStretch(c, 1 if c < cols else 0)
        self._grid_cols_max = max(cols, getattr(self, "_grid_cols_max", cols))
        rows = (len(self._quick_cards) + cols - 1) // cols
        for r in range(self._quick_grid.rowCount()):
            # Retired rows (a reflow from more columns to fewer leaves
            # empty rows behind — QGridLayout cannot delete them) MUST
            # drop their minimums again, or the stale floors inflate the
            # page's minimum past the scroll viewport (the V0.6.80
            # scrollbar catch). V0.6.84: the floor tracks the Round-4
            # density band (home_view._apply_grid_density owns the live
            # value; 84 is the constructor-time floor).
            self._quick_grid.setRowMinimumHeight(
                r, getattr(self, "_card_h", _CARD_H_MIN) if r < rows else 0
            )
            self._quick_grid.setRowStretch(r, 0)
        self.layout().activate()  # synchronous minimum refresh — see above

    def resizeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # V0.6.83 (Round-3 §6): the hero height is BODY-driven — ~0.325 of
        # the scroll viewport's height (see _hero_target_h), replacing the
        # V0.6.78 width-share rule. The V0.6.81 guarantee stays: MINIMUM,
        # not fixed — a taller font stack stretches the hero instead of
        # clipping the text column.
        hero_h = self._hero_target_h()
        if getattr(self, "_hero", None) is not None and getattr(self, "_hero_h", None) != hero_h:
            self._hero_h = hero_h
            self._hero.setMinimumHeight(hero_h)
        # V0.6.79 (spec P2) + V0.6.83: the hero's typography AND rhythm
        # scale with the hero target (see _scale_hero_typography).
        self._scale_hero_typography()
        # V0.6.84 (Round-4 §2.2): the card density band follows the body
        # (84 compact ↔ 122 reference) before the reflow reads row floors.
        self._apply_grid_density()
        # Spec §7: the illustration yields at narrow widths so the hero
        # text keeps its room (re-scaling when the size bucket changes);
        # spec §6: the grid reflows with width.
        self._apply_hero_pixmap()
        self._relayout_quick_grid()

    def _scale_hero_typography(self) -> None:
        """Scale the hero's display type AND rhythm with the Round-3 hero
        target (V0.6.83, spec §6).

        The scale s = hero_target / 336 (the reference rhythm's height),
        additionally capped by the width fit (the V0.6.79 rule: a 41 px
        headline cannot fit a 217 px column) and floored at 55% — the
        hierarchy is preserved at every supported size. Everything in the
        text column tracks s: the rhythm spacers, the eyebrow/headline/
        support sizes, the CTA's QSS padding (its 44 px touch floor holds),
        and the wrap caps so the words always fit their column."""
        from ui_qt.theme import FONT

        if getattr(self, "_hero_heading", None) is None:
            return
        hero_h = self._hero_target_h()
        scale = max(0.55, min(1.0, min(hero_h / _HERO_RHYTHM_BASE_H, self.width() / 1180)))
        # _HERO_HEADLINE_PX (V0.6.81): the measured fit for the reference's
        # exact two-line break — see the constant's note.
        hero_px = max(22, round(_HERO_HEADLINE_PX * scale))
        support_px = max(13, round(FONT.body_lg * scale))
        eyebrow_px = max(10, round(14 * scale))
        cta_px = max(12, round(16 * scale))
        # V0.6.81: the wrap caps are re-applied on EVERY call — the cap is
        # a maximum, so a stale value never clips text, but re-applying
        # keeps the intended 2-line wrap tuning as the column narrows.
        col = max(160, self.width() - 90)
        self._hero_heading.setMaximumWidth(max(200, min(round(545 * scale), col)))
        # V0.6.84.1 (Round-4 follow-up): the support cap is FLOORED at the
        # pinned first line's measured advance — the V0.6.81 hard newline
        # ("…summarized, organized\nand ready…") only renders as the
        # reference's two lines while the cap can hold line 1 whole; at
        # the field window the scaled cap (325 px) sat 6 px under the
        # 13 px line (331 px) and the label re-wrapped into a ragged
        # three lines with "organized" orphaned. When the column itself
        # is narrower than the line, the cap stays at the column (the
        # wrap is then unavoidable and word-level, never a clip).
        support = getattr(self, "_hero_support", None)
        if support is not None:
            l1 = support.fontMetrics().horizontalAdvance(
                "Books, articles and documents — summarized, organized"
            )
            support_cap = max(190, min(round(520 * scale), col))
            support.setMaximumWidth(max(support_cap, min(l1 + 4, col)))
        state = (
            hero_px,
            support_px,
            eyebrow_px,
            cta_px,
            round(scale * 100),
            # V0.6.84 (Round-4 §9, the dark-theme hero fix): the ACTIVE
            # THEME MODE joins the state tuple — refresh_theme() calls
            # through here on every toggle, and without the mode in the
            # key the guard skipped the re-apply (the palette colours in
            # these per-widget stylesheets went stale: charcoal headline
            # ink rendering on the dark hero ground — the pre-existing
            # defect visible in the V0.6.83 now4_dark.png evidence).
            theme_manager.mode,
        )
        if getattr(self, "_hero_scale", None) == state:
            return
        self._hero_scale = state
        p = theme_manager.palette
        self._hero_heading.setStyleSheet(
            f"font-size: {hero_px}px; font-weight: 600;"
            f"color: {p.text_primary}; background: transparent;"
        )
        self._hero_support.setStyleSheet(
            f"font-size: {support_px}px; color: {p.text_secondary}; background: transparent;"
        )
        # The eyebrow (tracked uppercase) — the QSS #Eyebrow rule carries
        # the tracking; the per-widget override only retunes the size.
        self._hero_rhythm_scale = scale
        eyebrow = getattr(self, "_hero_eyebrow", None)
        if eyebrow is not None:
            eyebrow.setStyleSheet(
                f"font-size: {eyebrow_px}px; font-weight: 600;"
                f"color: {p.sage}; background: transparent;"
            )
        # The CTA: QSS padding/typography scale with s (the 44 px touch
        # floor from _build_hero holds); the capsule painter follows the
        # widget rect at any height. V0.6.84: the trailing arrow's
        # inset/length/head track the SAME scale (the reference's
        # 26/9/5 at s=1.0) so the glyph never collides with the label.
        pad_v = max(9, round(15 * scale))
        pad_h = max(28, round(48 * scale))
        if getattr(self, "cta_btn", None) is not None:
            self.cta_btn.setStyleSheet(
                f"padding: {pad_v}px {pad_h}px; font-size: {cta_px}px;font-weight: 600;"
            )
            self.cta_btn._arrow_inset = max(14.0, round(26 * scale))
            self.cta_btn._arrow_len = max(6.0, round(9 * scale))
            self.cta_btn._arrow_head = max(3.5, round(5 * scale))
        # The rhythm spacers (V0.6.83): every gap in the text column scales
        # with s — changeSize + activate refreshes the layout minimum
        # synchronously (same contract as _lay_grid_columns).
        spacers = getattr(self, "_hero_spacers", None) or []
        for item, base in spacers:
            item.changeSize(0, max(1, round(base * scale)))
        if spacers and self.layout() is not None:
            self.layout().activate()

    # ══════════════════════════════════════════════════════════════════════
    # Theme refresh (the M0 §6 gap list — the M2 surfaces join the
    # refresh-on-toggle path)
    # ══════════════════════════════════════════════════════════════════════
    def refresh_theme(self) -> None:
        """Re-apply theme-dependent bits: the CTA glyph re-tints, the hero
        text column re-styles (V0.6.84: _scale_hero_typography carries the
        theme mode in its state key, so a toggle re-applies the palette
        colours — the fix for the stale charcoal ink on the dark hero),
        and the Quick Tool cards re-tint (all other chrome is QSS-driven
        and re-polishes globally). V0.6.83: the hero illustration is a
        TRANSPARENT pixmap — nothing re-composites on a toggle (the
        _apply_hero_pixmap call below is kept for the narrow-width hide
        rule's sake; it is a no-op while the budget key is unchanged)."""
        self._apply_hero_pixmap()
        self._scale_hero_typography()
        self._set_cta_icon()
        for card in self._quick_cards:
            card.refresh_theme()


__all__ = ["HomeView"]
