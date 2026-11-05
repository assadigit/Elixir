"""StageBar — the wizard's grouped stage-chip progress header (V0.7.0, V1).

The Round-2 rework item 2a: replaces the 42px dot strip
(``wizard_view.py``'s ``●`` + 10px-label rows). The wizard's 10 steps
group into 5 named stages (SOURCE · OUTPUTS · MODELS · TUNING · REVIEW);
each stage renders a small-caps label over a segmented track — one
segment per step in that stage — plus a muted sub-caption of the
stage's step names. Presentation only: every step keeps its identity
(Round-2 plan D1); the wizard's step indices are unchanged.

Anatomy (fixed row heights keep every stage column, and the thin
inter-stage connectors, pixel-aligned on the track row)::

    SOURCE            small-caps IBM Plex Sans SemiBold 11px label
    ▄▄▄ ▄▄▄ ▄▄▄       segmented track — one segment per step
    pdf · range · ocr sub-caption (drops out below 780px width)

Segment states — token-driven via ``theme_manager.palette`` (the plan's
"amber" is realised as the palette's accent token so BOTH themes stay
correct; no raw hex values live here):

* ``done``    — filled accent segment + check glyph
* ``current`` — accent-soft fill + a subtle accent emphasis ring
* ``future``  — muted hairline outline

The current stage's label takes the accent colour (semibold); completed
stages render in secondary text, future stages in muted text. Hovering a
stage shows a tooltip listing that stage's steps. Below 780px the
sub-captions drop and the bar tightens its margins (the compact form).

Reusable + AST-pinnable + offscreen-renderable: ``WizardView`` consumes
it, the state-transition sweep is a plain ``set_current_step`` call, and
``segment_state()`` exposes every segment's state for tests.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.theme import FONT, SPACE, WEIGHT, theme_manager

# Fixed row heights (px) — the alignment contract between stage columns
# and the inter-stage connectors.
_LABEL_H = 16
_TRACK_H = 16
_CAPTION_H = 14
_SEG_MIN_W = 18
_SEG_SPACING = 3
# Below this width the sub-captions drop and the bar compresses (plan 2a).
_COMPACT_WIDTH = 780


class StageSpec:
    """One named stage: its display name + the short names of its steps.

    ``name`` is shown small-caps (uppercased + letter-spaced here);
    ``steps`` carries the short per-step labels used for the sub-caption
    and the hover tooltip. The ORDER of stages + steps is the wizard's
    step order — ``StageBar.set_current_step`` takes a global step index
    across all stages' steps concatenated.
    """

    __slots__ = ("name", "steps")

    def __init__(self, name: str, steps: Sequence[str]) -> None:
        self.name = str(name)
        self.steps = tuple(str(s) for s in steps)


class _Segment(QFrame):
    """One step's segment inside a stage track (state-styled QFrame)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StageSegment")
        self.setFixedHeight(_TRACK_H)
        self.setMinimumWidth(_SEG_MIN_W)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.glyph = QLabel("")
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(self.glyph)
        self._state = "future"
        self._apply_state("future")

    @property
    def state(self) -> str:
        """``"done"`` | ``"current"`` | ``"future"`` — the test hook."""
        return self._state

    def _apply_state(self, state: str) -> None:
        p = theme_manager.palette
        self._state = state
        if state == "done":
            # Filled accent segment + check glyph.
            self.glyph.setText("✓")
            self.glyph.setStyleSheet(
                f"color: {p.text_on_accent}; background: transparent;"
                f" border: none; font-size: 9px; font-weight: 700;"
            )
            self.setStyleSheet(
                f"QFrame#StageSegment {{ background: {p.accent};"
                f" border: none; border-radius: 3px; }}"
            )
        elif state == "current":
            # Accent-soft fill + the subtle emphasis ring.
            self.glyph.setText("")
            self.setStyleSheet(
                f"QFrame#StageSegment {{ background: {p.accent_soft};"
                f" border: 2px solid {p.accent}; border-radius: 3px; }}"
            )
        else:
            # Muted hairline outline — a future step.
            self.glyph.setText("")
            self.setStyleSheet(
                f"QFrame#StageSegment {{ background: transparent;"
                f" border: 1px solid {p.border}; border-radius: 3px; }}"
            )


class StageBar(QWidget):
    """The grouped stage-chip progress header (V0.7.0, V1 — plan 2a).

    Build with the stage list, then drive it with the wizard's current
    step index::

        bar = StageBar([StageSpec("Source", ("PDF", "Range", "OCR")), ...])
        bar.set_current_step(4)   # global 0-based step index
    """

    def __init__(self, stages: Sequence[StageSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StageBar")
        self._stages = [StageSpec(s.name, s.steps) for s in stages]
        self._current = 0
        self._compact = False

        self._segments: list[list[_Segment]] = []
        self._labels: list[QLabel] = []
        self._captions: list[QLabel] = []
        self._connectors: list[QFrame] = []

        self.setFixedHeight(_LABEL_H + _TRACK_H + _CAPTION_H + 2 * SPACE.sm)
        root = QHBoxLayout(self)
        root.setContentsMargins(SPACE.xxl, SPACE.sm, SPACE.xxl, SPACE.sm)
        root.setSpacing(SPACE.md)

        for i, spec in enumerate(self._stages):
            if i > 0:
                root.addWidget(self._build_connector())
            root.addWidget(self._build_stage(spec), 1 if len(spec.steps) > 1 else 1)
        self._apply_states()

    # ── construction helpers ──────────────────────────────────────────

    def _build_stage(self, spec: StageSpec) -> QWidget:
        col = QWidget()
        col.setToolTip(f"{spec.name}: {', '.join(spec.steps)}")
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        label = QLabel(spec.name.upper())
        label.setFixedHeight(_LABEL_H)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._labels.append(label)
        v.addWidget(label)

        track = QWidget()
        track.setFixedHeight(_TRACK_H)
        t = QHBoxLayout(track)
        t.setContentsMargins(0, 0, 0, 0)
        t.setSpacing(_SEG_SPACING)
        segs: list[_Segment] = []
        for step_name in spec.steps:
            seg = _Segment()
            seg.setToolTip(f"{spec.name} — {step_name}")
            segs.append(seg)
            t.addWidget(seg)
        self._segments.append(segs)
        v.addWidget(track)

        # Sub-caption: the stage's step names (single-step stages keep the
        # row as a fixed-height placeholder so all tracks stay aligned —
        # the plan's sketch shows captions only on the multi-step stages).
        caption = QLabel(" · ".join(spec.steps) if len(spec.steps) > 1 else "")
        caption.setFixedHeight(_CAPTION_H)
        self._captions.append(caption)
        v.addWidget(caption)
        return col

    def _build_connector(self) -> QWidget:
        """The thin connector between stages (the user's sketch's ``---``)."""
        conn = QWidget()
        conn.setFixedWidth(14)
        c = QVBoxLayout(conn)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(0)
        c.addSpacing(_LABEL_H + _TRACK_H // 2 - 1)
        line = QFrame()
        line.setFixedSize(14, 2)
        line.setObjectName("StageConnector")
        self._connectors.append(line)
        c.addWidget(line)
        return conn

    # ── public API ────────────────────────────────────────────────────

    @property
    def stage_count(self) -> int:
        return len(self._stages)

    @property
    def step_count(self) -> int:
        return sum(len(segs) for segs in self._segments)

    def set_current_step(self, index: int) -> None:
        """Set the current step by its GLOBAL 0-based index (wizard order).

        Segments before the index render ``done`` (check glyph), the index
        itself renders ``current`` (emphasis ring), the rest ``future``.
        """
        self._current = int(index)
        self._apply_states()

    def segment_state(self, stage_i: int, step_i: int) -> str:
        """The state of one segment — ``"done"``/``"current"``/``"future"``."""
        return self._segments[stage_i][step_i].state

    def is_compact(self) -> bool:
        """Whether the bar is in its narrow (sub-captions dropped) form."""
        return self._compact

    def set_compact(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        for cap in self._captions:
            cap.setVisible(not compact)
        root = self.layout()
        if root is not None:
            m = SPACE.md if compact else SPACE.xxl
            root.setContentsMargins(m, SPACE.sm, m, SPACE.sm)

    def refresh_theme(self) -> None:
        """Re-apply every palette-dependent style (theme toggle hook)."""
        self._apply_states()

    # ── internals ─────────────────────────────────────────────────────

    def _apply_states(self) -> None:
        p = theme_manager.palette
        pos = 0
        for stage_i, segs in enumerate(self._segments):
            stage_start = pos
            for seg in segs:
                if pos < self._current:
                    seg._apply_state("done")
                elif pos == self._current:
                    seg._apply_state("current")
                else:
                    seg._apply_state("future")
                pos += 1
            stage_end = pos  # exclusive
            label = self._labels[stage_i]
            if stage_start <= self._current < stage_end:
                # The current stage — accent colour, semibold.
                label.setStyleSheet(
                    f"font-size: {FONT.subhead}px; font-weight: {WEIGHT.semibold};"
                    f" letter-spacing: 0.8px; color: {p.accent};"
                    f" background: transparent;"
                )
            elif stage_end <= self._current:
                label.setStyleSheet(
                    f"font-size: {FONT.subhead}px; font-weight: {WEIGHT.semibold};"
                    f" letter-spacing: 0.8px; color: {p.text_secondary};"
                    f" background: transparent;"
                )
            else:
                label.setStyleSheet(
                    f"font-size: {FONT.subhead}px; font-weight: {WEIGHT.semibold};"
                    f" letter-spacing: 0.8px; color: {p.text_muted};"
                    f" background: transparent;"
                )
            self._captions[stage_i].setStyleSheet(
                f"font-size: {FONT.caption}px; color: {p.text_muted}; background: transparent;"
            )
        for line in self._connectors:
            line.setStyleSheet(f"QFrame#StageConnector {{ background: {p.border}; border: none; }}")

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Below 780px the sub-captions drop (the compact form, plan 2a)."""
        self.set_compact(self.width() < _COMPACT_WIDTH)
        super().resizeEvent(event)
