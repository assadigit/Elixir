"""V10.19.0: Token cost estimation dialog — shown before conversion starts.

A modal dialog that shows the estimated token usage for the upcoming
conversion, broken down by output type.  The user can confirm or cancel.

V13.31.0 (#14): The automatic cost estimation (based on a static provider
  pricing table) has been **removed** — it was unreliable. The dialog now
  shows **token counts only** and provides a manual **"Cost per million
  tokens ($):"** input field. The user enters their actual provider
  pricing and the dialog calculates the total cost live::

      total_cost = (total_tokens / 1_000_000) * user_entered_cost

V18.15.3.2: FIXED the dialog height bug. The dialog used to grow taller
  with more content (more chapters = more rows), pushing the Proceed
  button off-screen on smaller monitors. Now the dialog has a FIXED
  landscape size (680x560) with a SCROLLABLE content area and the
  buttons PINNED to the bottom (always visible). The content area uses
  a QScrollArea so it can scroll if the content exceeds the fixed height.

Usage::

    from ui_qt.views.token_cost_dialog import TokenCostDialog
    dlg = TokenCostDialog(estimate, parent)
    if dlg.exec() == QDialog.Accepted:
        # proceed with conversion
    else:
        # user cancelled
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class TokenCostDialog(QDialog):
    """Pre-conversion token cost estimation dialog.

    Shows:
      - Total estimated tokens (input + output)
      - PDF pages + source tokens
      - Estimated chapter count
      - Estimated LLM API calls
      - Breakdown by output type

    V13.31.0 (#14): Adds a manual "Cost per million tokens ($):" input
    field. The user enters their actual provider pricing (e.g. $0.15 for
    OpenAI gpt-4o-mini) and the dialog calculates the live total cost.

    V13.36.0: When chapters are selected, the PRIMARY headline shows the
    SELECTED chapters' token cost (large 22px), with the FULL BOOK total
    as a secondary muted line below. The cost calculator also tracks the
    selected total (so the user's manual cost-per-million multiplies the
    right base).

    V18.15.3.2: Fixed-size landscape dialog (680x560) with scrollable
    content + pinned buttons. No more "Proceed button off-screen" bug.
    """

    # V18.15.3.2: Fixed landscape dimensions — wide enough for the stats
    # table, short enough to fit on a 768px-tall laptop screen with room
    # for the title bar + taskbar. Content scrolls if it overflows.
    # V18.15.9.1: Raised height 560 → 640 to fix the "Cost Calculator (manual)"
    # group box being cut off at the bottom (the V18.15.9.0 audit screenshot
    # showed the formula_note text truncated). Width unchanged at 680.
    # V18.20.3.8: the height is now a PREFERRED value, capped to the screen's
    # available geometry (see _apply_size_caps) — on Windows DPI scaling of
    # 125–150% a fixed 640px-logical dialog + title bar + taskbar can exceed
    # the visible screen and clip the pinned Cancel/Proceed bar off-screen
    # (the "not enough space for buttons" rig report).
    _DLG_WIDTH = 680
    _DLG_HEIGHT = 640
    _DLG_MIN_HEIGHT = 420

    def __init__(self, estimate: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Token Cost Estimation")
        self.setModal(True)

        # V18.15.3.2: Fixed landscape size — no more unbounded growth.
        # V18.20.3.8: fixed WIDTH only; height capped to the target screen.
        self.setFixedWidth(self._DLG_WIDTH)
        self._apply_size_caps()

        self._estimate = estimate
        # V13.36.0: If chapters are selected, the primary total is the
        # selected-chapters total; otherwise it's the full-book total.
        selected_total = estimate.get("selected_total_tokens", 0)
        if selected_total and selected_total > 0:
            self._total_tokens: int = int(selected_total)
            self._has_selection = True
        else:
            self._total_tokens: int = int(estimate.get("total_tokens", 0) or 0)
            self._has_selection = False
        self._build_ui()

    def _apply_size_caps(self):
        """V18.20.3.8: cap the dialog height to the screen it will show on.

        setFixedSize(680, 640) assumed ~640 logical px of vertical room.
        With Windows display scaling at 125–150% (the rig: 1920×1080 @150%
        = 1280×720 logical), 640 + title bar + taskbar overflows the visible
        area and the PINNED button bar is cut off below the screen edge.
        The height now prefers 640 but never exceeds the screen's available
        geometry; content scrolls either way (that is what the QScrollArea
        is for), so no information is lost on small screens.
        """
        max_h = self._DLG_HEIGHT
        try:
            from PySide6.QtGui import QGuiApplication
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                if avail.height() > 0:
                    # 48 px of headroom for the title bar + a small margin.
                    max_h = avail.height() - 48
        except Exception:
            pass  # no screen info (headless test) — use the preferred height
        height = max(self._DLG_MIN_HEIGHT, min(self._DLG_HEIGHT, max_h))
        self.setFixedHeight(int(height))

    def _build_ui(self):
        # V18.15.3.2: Two-zone layout:
        #   [QScrollArea — all content (header + stats + breakdown + cost)]
        #   [QHBoxLayout — Cancel + Proceed buttons (pinned to bottom)]
        # This ensures the buttons are ALWAYS visible regardless of content size.
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Scrollable content area ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        # V18.20.3.8: objectName-scoped rule. The previous bare
        # `QWidget { background: transparent; }` selector matched EVERY
        # descendant (QGroupBox, QPushButton, …). Widget-level stylesheets
        # take precedence over the application stylesheet, so it silently
        # KILLED the theme's QPushButton#Primary/#Secondary styling for
        # every button in the scroll content. Scoping to the objectName
        # styles only this container.
        content.setObjectName("CostDialogContent")
        content.setStyleSheet(
            "QWidget#CostDialogContent { background: transparent; }"
        )
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 16, 20, 12)

        self._build_header(lay)
        self._build_stats(lay)
        self._build_breakdown(lay)
        self._build_cost_calculator(lay)
        self._build_per_output(lay)
        self._build_warning(lay)

        lay.addStretch()  # push content to top

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)  # stretch=1 → takes all available space

        # ── Pinned button bar (always visible) ───────────────────────
        self._build_buttons(outer)

        # V13.31.0 (#14): Initial cost calculation (with default 0.0)
        self._recalculate_cost()

    def _build_header(self, lay: QVBoxLayout):
        """V13.36.0: Two-tier headline — selected chapters as primary."""
        if self._has_selection:
            selected_count = self._estimate.get("selected_chapter_count", 0)
            selected_total = self._estimate.get("selected_total_tokens", 0)
            full_total = self._estimate.get("total_tokens", 0)
            full_chapters = self._estimate.get("full_book_chapter_count",
                                                self._estimate.get("chapter_count", 0))

            header = QLabel("📊 This conversion will use approximately:")
            header.setStyleSheet("font-size: 14px; font-weight: bold;")
            lay.addWidget(header)

            # PRIMARY: selected chapters (large 22px)
            primary_label = QLabel(
                f"<span style='font-size: 22px; font-weight: bold;'>{selected_total:,}</span> tokens"
            )
            primary_label.setAlignment(Qt.AlignCenter)
            primary_label.setStyleSheet("padding: 8px;")
            lay.addWidget(primary_label)

            # Caption: "for N selected chapter(s)"
            caption = QLabel(f"for {selected_count} selected chapter(s)")
            caption.setAlignment(Qt.AlignCenter)
            caption.setStyleSheet("color: #5B9BD5; font-size: 12px; font-weight: bold; padding-bottom: 4px;")
            lay.addWidget(caption)

            # SECONDARY: full book (muted, smaller)
            if full_total and full_total != selected_total:
                secondary = QLabel(
                    f"<span style='color: #999;'>Full book (~{full_chapters} chapters): "
                    f"{full_total:,} tokens</span>"
                )
                secondary.setAlignment(Qt.AlignCenter)
                secondary.setStyleSheet("font-size: 11px; padding: 2px;")
                lay.addWidget(secondary)

            # Show first few selected chapter titles
            titles = self._estimate.get("selected_chapter_titles", [])
            if titles:
                titles_str = "  ·  ".join(titles[:3])
                if len(titles) > 3:
                    titles_str += f"  ·  (+{len(titles) - 3} more)"
                titles_label = QLabel(f"<i>{titles_str}</i>")
                titles_label.setStyleSheet("color: #666; font-size: 10px; padding: 4px 8px;")
                titles_label.setWordWrap(True)
                titles_label.setAlignment(Qt.AlignCenter)
                lay.addWidget(titles_label)
        else:
            # No selection — show full-book total as before
            total = self._estimate.get("total_tokens", 0)
            header = QLabel("📊 This conversion will use approximately:")
            header.setStyleSheet("font-size: 14px; font-weight: bold;")
            lay.addWidget(header)

            total_label = QLabel(f"<span style='font-size: 22px; font-weight: bold;'>{total:,}</span> tokens")
            total_label.setAlignment(Qt.AlignCenter)
            total_label.setStyleSheet("padding: 8px;")
            lay.addWidget(total_label)

    def _build_stats(self, lay: QVBoxLayout):
        """Summary stats group box."""
        stats_group = QGroupBox("Summary")
        stats_lay = QFormLayout(stats_group)
        stats_lay.setSpacing(4)

        if self._has_selection:
            stats_lay.addRow("Selected chapters:", QLabel(str(self._estimate.get("selected_chapter_count", "?"))))
            stats_lay.addRow("Selected source:", QLabel(f"{self._estimate.get('selected_source_tokens', 0):,} tokens"))
            stats_lay.addRow("Selected LLM calls:", QLabel(str(self._estimate.get("selected_llm_calls", "?"))))
            stats_lay.addRow("Avg tokens/selected ch:", QLabel(f"{self._estimate.get('selected_avg_chapter_tokens', 0):,}"))
            stats_lay.addRow("━━━━━━━━━━━━━━━", QLabel("━━━━━━━━━━━━━━━"))
            stats_lay.addRow("Full book chapters:", QLabel(str(self._estimate.get("full_book_chapter_count", "?"))))
            stats_lay.addRow("PDF pages:", QLabel(str(self._estimate.get("pdf_pages", "?"))))
            stats_lay.addRow("Full book source:", QLabel(f"{self._estimate.get('source_tokens', 0):,} tokens"))
        else:
            stats_lay.addRow("PDF pages:", QLabel(str(self._estimate.get("pdf_pages", "?"))))
            stats_lay.addRow("Source text:", QLabel(f"{self._estimate.get('source_tokens', 0):,} tokens"))
            stats_lay.addRow("Extracted chars:", QLabel(f"{self._estimate.get('extracted_chars', 0):,}"))
            stats_lay.addRow("Est. chapters:", QLabel(str(self._estimate.get("chapter_count", "?"))))
            stats_lay.addRow("Est. LLM calls:", QLabel(str(self._estimate.get("llm_calls", "?"))))
            stats_lay.addRow("Avg tokens/chapter:", QLabel(f"{self._estimate.get('avg_chapter_tokens', 0):,}"))

        lay.addWidget(stats_group)

    def _build_breakdown(self, lay: QVBoxLayout):
        """Token breakdown group box."""
        if self._has_selection:
            input_tokens = self._estimate.get("selected_input_tokens", 0)
            output_tokens = self._estimate.get("selected_output_tokens", 0)
            total = self._estimate.get("selected_total_tokens", 0)
            breakdown_title = "Token Breakdown (Selected)"
        else:
            input_tokens = self._estimate.get("input_tokens", 0)
            output_tokens = self._estimate.get("output_tokens", 0)
            total = self._estimate.get("total_tokens", 0)
            breakdown_title = "Token Breakdown"

        breakdown_group = QGroupBox(breakdown_title)
        breakdown_lay = QFormLayout(breakdown_group)
        breakdown_lay.setSpacing(4)

        breakdown_lay.addRow("📥 Input (source + prompts):", QLabel(f"{input_tokens:,} tokens"))
        breakdown_lay.addRow("📤 Output (summaries + outputs):", QLabel(f"{output_tokens:,} tokens"))
        breakdown_lay.addRow("━━━━━━━━━━━━━━━", QLabel("━━━━━━━━━━━━━━━"))
        breakdown_lay.addRow("Total:", QLabel(f"<b>{total:,} tokens</b>"))

        lay.addWidget(breakdown_group)

    def _build_cost_calculator(self, lay: QVBoxLayout):
        """V13.31.0 (#14): Manual cost calculator."""
        cost_group = QGroupBox("Cost Calculator (manual)")
        cost_lay = QFormLayout(cost_group)
        cost_lay.setSpacing(4)

        self.cost_per_million_spin = QDoubleSpinBox()
        self.cost_per_million_spin.setRange(0.0, 100_000.0)
        self.cost_per_million_spin.setDecimals(6)
        self.cost_per_million_spin.setSingleStep(0.10)
        self.cost_per_million_spin.setValue(0.0)
        self.cost_per_million_spin.setPrefix("$ ")
        self.cost_per_million_spin.setSuffix(" / 1M tokens")
        self.cost_per_million_spin.setToolTip(
            "Enter your provider's actual cost per million tokens.\n\n"
            "Examples (these are illustrative — check your provider's pricing page):\n"
            "  • Ollama (local): $0.0\n"
            "  • OpenAI gpt-4o-mini: $0.15 input / $0.60 output (use a blended average)\n"
            "  • Anthropic Claude 3.5 Sonnet: $3.00 input / $15.00 output\n"
        )
        self.cost_per_million_spin.valueChanged.connect(self._recalculate_cost)
        cost_lay.addRow("Cost per million tokens ($):", self.cost_per_million_spin)

        self.total_cost_label = QLabel("<b>$0.00</b> (enter a cost above to estimate)")
        self.total_cost_label.setStyleSheet("padding: 4px;")
        cost_lay.addRow("Estimated cost:", self.total_cost_label)

        formula_note = QLabel(
            "Formula: total_cost = (total_tokens / 1,000,000) × cost_per_million\n"
            "V13.31.0 (#14): The automatic provider-pricing estimate was removed — "
            "it was unreliable. Enter your actual provider pricing here for an "
            "exact calculation."
        )
        formula_note.setStyleSheet("color: palette(text-muted); font-size: 10px;")
        formula_note.setWordWrap(True)
        cost_lay.addRow("", formula_note)
        lay.addWidget(cost_group)

    def _build_per_output(self, lay: QVBoxLayout):
        """Per-output breakdown group box."""
        per_output = self._estimate.get("per_output", {})
        if per_output:
            output_group = QGroupBox("Per-Output Breakdown")
            output_lay = QFormLayout(output_group)
            output_lay.setSpacing(2)
            for name, tokens in sorted(per_output.items(), key=lambda x: -x[1]):
                label = QLabel(f"{tokens:,} tokens")
                label.setStyleSheet("color: palette(text-muted);")
                output_lay.addRow(f"  {name}:", label)
            lay.addWidget(output_group)

    def _build_warning(self, lay: QVBoxLayout):
        """Large-conversion warning for cloud users."""
        total = self._total_tokens
        if total > 100000:
            warning = QLabel(
                "⚠️ This is a large conversion. If using a cloud API, "
                "this may cost significant tokens. Proceed with caution."
            )
            warning.setStyleSheet("color: #e67e22; font-size: 11px;")
            warning.setWordWrap(True)
            lay.addWidget(warning)

    def _build_buttons(self, outer: QVBoxLayout):
        """V18.15.3.2: Pinned button bar — always visible at the bottom."""
        btn_bar = QWidget()
        # V18.20.3.8: objectName-scoped rule — SAME root cause as the
        # V18.17.0.0 "text-align" fix, one level up: this bare
        # `QWidget { background: palette(window); border-top: … }` selector
        # matched the Cancel/Proceed buttons too (QPushButton is-a QWidget)
        # and, because widget-level stylesheets take precedence over the
        # application stylesheet, it OVERRID the theme's
        # QPushButton#Primary terracotta fill ("Proceed has no fill color,
        # glitchy" on the rig) and the Secondary outline. Scoping the rule
        # to the bar's objectName restores the unified CTA styling.
        btn_bar.setObjectName("CostDialogBtnBar")
        btn_bar.setStyleSheet(
            "QWidget#CostDialogBtnBar { background: palette(window); "
            "border-top: 1px solid palette(mid); }"
        )
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setSpacing(12)  # V18.17.0.0: increased spacing between buttons
        btn_layout.setContentsMargins(20, 12, 20, 14)  # V18.20.3.8: a touch more bottom padding

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setMinimumHeight(36)  # V18.20.3.8: match Proceed — a balanced pair
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        proceed_btn = QPushButton("✅ Proceed")
        proceed_btn.setObjectName("Primary")
        proceed_btn.setCursor(Qt.PointingHandCursor)
        # V18.17.0.0 (Fix): Removed setStyleSheet("text-align: center;") — it was
        # OVERRIDING the theme's QPushButton#Primary styling (terracotta background,
        # padding, border-radius), making the button light/default. The theme's
        # `padding: 7px 18px` already centers the text naturally. The setMinimumWidth
        # gives the button enough horizontal space.
        proceed_btn.setMinimumWidth(140)
        proceed_btn.setMinimumHeight(36)
        proceed_btn.setDefault(True)  # V18.20.3.8: Enter key proceeds
        proceed_btn.clicked.connect(self.accept)
        btn_layout.addWidget(proceed_btn)

        outer.addWidget(btn_bar)  # no stretch → fixed height at bottom

    def _recalculate_cost(self) -> None:
        """Recalculate the total cost from the user-entered per-million rate.

        Formula: total_cost = (total_tokens / 1_000_000) * user_entered_cost
        """
        rate = self.cost_per_million_spin.value()
        if rate <= 0:
            self.total_cost_label.setText(
                "<b>$0.00</b> (enter a cost above to estimate)"
            )
            return
        total_cost = (self._total_tokens / 1_000_000) * rate
        self.total_cost_label.setText(
            f"<b>${total_cost:,.2f}</b> (based on your input)"
        )
