"""V10.28.0 (Sprint 1.5): Quarantine panel — review & restore dropped bullets.

This tab reads ``output/<book>/logs/drops.jsonl`` (written by
:class:`core.summarisation.quarantine.QuarantineLog`) and presents every
dropped bullet in a filterable table.  Each row shows:

- the bullet text (truncated for the column, full text in the tooltip)
- the pipeline stage that dropped it (F4 / Phase 2.2 / B3 dedup / Judge / …)
- the human-readable reason
- the measured source-overlap (0–100%)
- the status (Dropped / Logged-only (conservative) / Recovered)
- a **Restore** button (re-marks the bullet as recovered on disk)

The Restore button writes ``recovered: true`` back to ``drops.jsonl`` so the
audit trail stays honest — a manually-restored bullet is distinguishable
from an auto-recovered one (the recovery pass sets the same flag, but the
timestamp differs).

This view is read-only with respect to the live conversion — it does NOT
re-insert bullets into an already-generated keypoints file.  Restoring a
bullet here is an audit annotation; to actually regenerate the keypoints
with the bullet included, re-run the conversion (ideally in Conservative
mode so nothing is dropped).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.summarisation.quarantine import QuarantineLog
from ui_qt.components import Card, StepHeader
from ui_qt.theme import theme_manager

# Stage → (display label, colour-name in palette)
_STAGE_META = {
    "thinking_filter.thinking_process": ("Thinking process", "warning"),
    "thinking_filter.backtick_words": ("Backtick words", "warning"),
    "thinking_filter.internal_markers": ("Internal markers", "warning"),
    "thinking_filter.prompt_leakage": ("Prompt leakage", "warning"),
    "thinking_filter.meta_commentary": ("Meta commentary", "text_muted"),
    "thinking_filter.too_long_500chars": ("Too long (>500ch)", "text_muted"),
    "thinking_filter.narrative_no_concept": ("Narrative (no concept)", "text_muted"),
    "thinking_filter.numeric_verify": ("Numeric verify", "text_muted"),
    "quality_scorer": ("Quality scorer", "text_muted"),
    "F4_source_overlap": ("F4 source overlap", "error"),
    "Phase2.2_semantic_fact_check": ("Phase 2.2 fact-check", "error"),
    "B3_dedup": ("B3 dedup", "text_secondary"),
    "judge_grounding.llm_f4_crosscheck": ("Judge (LLM+F4)", "error"),
    "judge_grounding.verbatim_exempt": ("Judge (verbatim)", "error"),
    "judge_grounding.ungrounded": ("Judge (ungrounded)", "error"),
}


def _stage_label(stage: str) -> str:
    return _STAGE_META.get(stage, (stage or "unknown", "text_muted"))[0]


def _stage_color(stage: str) -> str:
    return _STAGE_META.get(stage, (stage or "unknown", "text_muted"))[1]


class QuarantineView(QWidget):
    """Tab for reviewing and restoring bullets dropped during conversion."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._drops_path: Path | None = None
        self._entries: list[dict[str, Any]] = []
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 6)
        root.setSpacing(7)

        # ── Header card: folder picker + load ───────────────────────────
        header_card = Card(padding=10, spacing=6)
        header_card.addWidget(
            StepHeader(
                number=0,
                title="Quarantine — dropped-bullet audit & restore",
                caption="Pick a book's output folder to review every bullet the "
                "pipeline dropped, why it was dropped, and restore any "
                "that should have survived.",
            )
        )

        pick_row = QHBoxLayout()
        pick_row.setSpacing(6)
        self.folder_btn = QPushButton("Pick book folder…")
        self.folder_btn.clicked.connect(self._pick_folder)
        pick_row.addWidget(self.folder_btn)

        self.auto_btn = QPushButton("Auto-detect latest")
        self.auto_btn.setToolTip(
            "Scan the controller's last output directory for a drops.jsonl file."
        )
        self.auto_btn.clicked.connect(self._auto_detect)
        pick_row.addWidget(self.auto_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._reload)
        pick_row.addWidget(self.refresh_btn)

        pick_row.addStretch()

        self.path_label = QLabel("No book folder selected.")
        self.path_label.setObjectName("Caption")
        pick_row.addWidget(self.path_label)

        header_card.addLayout(pick_row)

        # ── Summary stats line ──────────────────────────────────────────
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("Caption")
        self.stats_label.setWordWrap(True)
        header_card.addWidget(self.stats_label)

        # ── Stage filter ────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(QLabel("Filter by stage:"))
        self.stage_filter = QComboBox()
        self.stage_filter.addItem("(all stages)", "")
        self.stage_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.stage_filter)

        filter_row.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("(all)", "all")
        self.status_filter.addItem("Dropped only", "dropped")
        self.status_filter.addItem("Logged-only (conservative)", "logged")
        self.status_filter.addItem("Recovered", "recovered")
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.status_filter)

        filter_row.addStretch()
        self.export_btn = QPushButton("Export visible as JSON…")
        self.export_btn.clicked.connect(self._export_visible)
        filter_row.addWidget(self.export_btn)

        header_card.addLayout(filter_row)
        root.addWidget(header_card)

        # ── Table ───────────────────────────────────────────────────────
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Bullet", "Stage", "Reason", "Overlap", "Status", "Action"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setTextElideMode(Qt.ElideRight)
        root.addWidget(self.table, 1)

        # ── Empty-state hint ────────────────────────────────────────────
        self.empty_label = QLabel(
            "No drops loaded yet.  Convert a book (or pick its output folder) "
            "to see every bullet that was dropped — with the reason and a "
            "Restore button."
        )
        self.empty_label.setObjectName("Caption")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(True)
        root.addWidget(self.empty_label)

        root.addStretch()

    # ── loading ─────────────────────────────────────────────────────────

    def _pick_folder(self) -> None:
        start = self._guess_start_dir()
        folder = QFileDialog.getExistingDirectory(
            self, "Pick a book output folder", str(start) if start else ""
        )
        if folder:
            self._load_from_folder(Path(folder))

    def _auto_detect(self) -> None:
        """Try the controller's last output directory, else common roots."""
        candidates: list[Path] = []
        # 1. Controller's last-known output dir
        try:
            last = getattr(self.controller, "last_output_dir", None)
            if last:
                candidates.append(Path(last))
        except Exception:
            pass
        # 2. The input PDF's parent (most common layout)
        try:
            cv = getattr(self.controller, "convert_view", None)
            inp = getattr(cv, "state", None)
            if inp and getattr(inp, "input_path", ""):
                candidates.append(Path(inp.input_path).parent)
        except Exception:
            pass
        # 3. ~/Documents / cwd fallbacks
        candidates.append(Path.home() / "Documents")
        candidates.append(Path.cwd())

        for c in candidates:
            drops = QuarantineLog.find_drops_log(c)
            if drops:
                self._load_from_folder(c)
                return
        # Deep search one level: output/<book>/logs/drops.jsonl
        for c in candidates:
            if c and c.exists():
                for sub in c.iterdir():
                    if sub.is_dir():
                        drops = QuarantineLog.find_drops_log(sub)
                        if drops:
                            self._load_from_folder(sub)
                            return
        self.stats_label.setText("Auto-detect found no drops.jsonl.  Pick a book folder manually.")

    def _guess_start_dir(self) -> Path | None:
        try:
            last = getattr(self.controller, "last_output_dir", None)
            if last:
                return Path(last)
        except Exception:
            pass  # best-effort (UI — never crash)
        return None

    def _load_from_folder(self, folder: Path) -> None:
        drops = QuarantineLog.find_drops_log(folder)
        if not drops:
            self._drops_path = None
            self._entries = []
            self.path_label.setText(f"{folder} — no drops.jsonl found.")
            self.stats_label.setText(
                "This book either had no drops, or was converted before V10.28.0 "
                "(which introduced the quarantine log)."
            )
            self._render_table()
            return
        self._drops_path = drops
        self.path_label.setText(str(drops))
        self._reload()

    def _reload(self) -> None:
        if not self._drops_path:
            return
        self._entries = QuarantineLog.load_from_disk(self._drops_path)
        self._render_table()

    # ── rendering ───────────────────────────────────────────────────────

    def _render_table(self) -> None:
        # Rebuild the stage filter from the current entries.
        prev_stage = self.stage_filter.currentData()
        self.stage_filter.blockSignals(True)
        self.stage_filter.clear()
        self.stage_filter.addItem("(all stages)", "")
        stages_present = sorted({e.get("stage", "") for e in self._entries})
        for s in stages_present:
            self.stage_filter.addItem(_stage_label(s), s)
        # restore previous selection if still present
        if prev_stage:
            idx = self.stage_filter.findData(prev_stage)
            if idx >= 0:
                self.stage_filter.setCurrentIndex(idx)
        self.stage_filter.blockSignals(False)

        # Summary stats
        total = len(self._entries)
        dropped = sum(1 for e in self._entries if e.get("actually_dropped", True))
        logged_only = sum(1 for e in self._entries if not e.get("actually_dropped", True))
        recovered = sum(1 for e in self._entries if e.get("recovered", False))
        by_stage: dict[str, int] = {}
        for e in self._entries:
            st = e.get("stage", "unknown")
            by_stage[st] = by_stage.get(st, 0) + 1
        stage_str = ", ".join(
            f"{_stage_label(k)}: {v}" for k, v in sorted(by_stage.items(), key=lambda x: -x[1])
        )
        if total == 0:
            self.stats_label.setText(
                "No drops recorded for this book.  (Either the conversion had "
                "zero drops, or it ran before V10.28.0.)"
            )
        else:
            self.stats_label.setText(
                f"<b>{total}</b> drop(s) recorded &nbsp;·&nbsp; "
                f"<b>{dropped}</b> actually dropped &nbsp;·&nbsp; "
                f"<b>{logged_only}</b> logged-only (conservative) &nbsp;·&nbsp; "
                f"<b>{recovered}</b> recovered. &nbsp;&nbsp; "
                f"<i>{stage_str}</i>"
            )

        self._apply_filter()

    def _apply_filter(self) -> None:
        stage_sel = self.stage_filter.currentData() or ""
        status_sel = self.status_filter.currentData() or "all"

        visible = []
        for e in self._entries:
            st = e.get("stage", "")
            if stage_sel and st != stage_sel:
                continue
            rec = bool(e.get("recovered", False))
            ad = bool(e.get("actually_dropped", True))
            if status_sel == "dropped" and (not ad or rec):
                continue
            if status_sel == "logged" and (ad or rec):
                continue
            if status_sel == "recovered" and not rec:
                continue
            visible.append(e)

        self.table.setRowCount(0)
        self.table.setRowCount(len(visible))
        p = theme_manager.palette
        for row, e in enumerate(visible):
            bullet = str(e.get("bullet", ""))
            stage = str(e.get("stage", ""))
            reason = str(e.get("reason", ""))
            overlap = float(e.get("source_overlap", 0.0))
            recovered = bool(e.get("recovered", False))
            actually_dropped = bool(e.get("actually_dropped", True))
            chapter = str(e.get("chapter", ""))

            tip = (
                f"Bullet:\n{bullet}\n\n"
                f"Stage: {stage}\n"
                f"Reason: {reason}\n"
                f"Source overlap: {overlap:.1%}\n"
                f"Chapter: {chapter or '(unknown)'}\n"
                f"Recovered: {'yes' if recovered else 'no'}\n"
                f"Actually dropped: {'yes' if actually_dropped else 'no (logged in conservative mode)'}"
            )

            bp_item = QTableWidgetItem(bullet)
            bp_item.setToolTip(tip)
            bp_item.setData(Qt.UserRole, bullet)
            self.table.setItem(row, 0, bp_item)

            stage_item = QTableWidgetItem(_stage_label(stage))
            stage_item.setToolTip(tip)
            col = getattr(p, _stage_color(stage), p.text_secondary)
            stage_item.setForeground(_qcolor_from_hex(col))
            self.table.setItem(row, 1, stage_item)

            reason_item = QTableWidgetItem(reason)
            reason_item.setToolTip(tip)
            self.table.setItem(row, 2, reason_item)

            ov_item = QTableWidgetItem(f"{overlap:.0%}")
            ov_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ov_item.setToolTip(tip)
            self.table.setItem(row, 3, ov_item)

            if recovered:
                status_txt = "♻️ Recovered"
                status_col = p.success
            elif not actually_dropped:
                status_txt = "📋 Logged-only"
                status_col = p.text_muted
            else:
                status_txt = "🗑️ Dropped"
                status_col = p.error
            status_item = QTableWidgetItem(status_txt)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(_qcolor_from_hex(status_col))
            status_item.setToolTip(tip)
            self.table.setItem(row, 4, status_item)

            # Action button cell
            action_widget = QWidget()
            action_lay = QHBoxLayout(action_widget)
            action_lay.setContentsMargins(4, 2, 4, 2)
            action_lay.setSpacing(4)
            if recovered:
                lbl = QLabel("—")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                action_lay.addWidget(lbl)
            else:
                btn = QPushButton("Restore")
                btn.setToolTip(
                    "Mark this bullet as recovered in drops.jsonl.\n"
                    "Note: this is an audit annotation — to regenerate the "
                    "keypoints with this bullet included, re-run the conversion "
                    "(ideally in Conservative mode)."
                )
                btn.clicked.connect(lambda _=False, b=bullet, s=stage: self._restore(b, s))
                action_lay.addWidget(btn)
            action_lay.addStretch()
            self.table.setCellWidget(row, 5, action_widget)

        self.table.resizeRowsToContents()
        self.empty_label.setVisible(len(visible) == 0)
        if len(visible) == 0 and len(self._entries) > 0:
            self.empty_label.setText(
                "No drops match the current filter.  Change the stage/status filter."
            )
        elif len(visible) == 0:
            self.empty_label.setText(
                "No drops loaded yet.  Convert a book (or pick its output folder) "
                "to see every bullet that was dropped — with the reason and a "
                "Restore button."
            )

    # ── actions ─────────────────────────────────────────────────────────

    def _restore(self, bullet: str, stage: str) -> None:
        """Mark the first matching unrecovered entry as recovered on disk."""
        if not self._drops_path or not self._drops_path.exists():
            return
        try:
            lines = self._drops_path.read_text(encoding="utf-8").splitlines()
            updated = False
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    obj.get("bullet") == bullet
                    and obj.get("stage") == stage
                    and not obj.get("recovered", False)
                ):
                    obj["recovered"] = True
                    obj["manually_restored"] = True
                    lines[i] = json.dumps(obj, ensure_ascii=False)
                    updated = True
                    break
            if updated:
                self._drops_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                self._reload()
        except Exception as exc:
            self.stats_label.setText(f"⚠️ Failed to update drops.jsonl: {type(exc).__name__}: {exc}")

    def _export_visible(self) -> None:
        if not self._entries:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export visible drops", "drops_export.json", "JSON (*.json)"
        )
        if not dest:
            return
        stage_sel = self.stage_filter.currentData() or ""
        status_sel = self.status_filter.currentData() or "all"
        out = []
        for e in self._entries:
            st = e.get("stage", "")
            if stage_sel and st != stage_sel:
                continue
            rec = bool(e.get("recovered", False))
            ad = bool(e.get("actually_dropped", True))
            if status_sel == "dropped" and (not ad or rec):
                continue
            if status_sel == "logged" and (ad or rec):
                continue
            if status_sel == "recovered" and not rec:
                continue
            out.append(e)
        try:
            Path(dest).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stats_label.setText(f"Exported {len(out)} drop(s) to {dest}.")
        except Exception as exc:
            self.stats_label.setText(f"⚠️ Export failed: {type(exc).__name__}: {exc}")

    # ── theme ───────────────────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """Re-render so palette-dependent colours update on theme toggle."""
        self._render_table()


# ── helpers ─────────────────────────────────────────────────────────────────


def _qcolor_from_hex(hex_str: str):
    """Convert a #RRGGBB palette colour into a QColor (lazy import of QtGui)."""
    try:
        from PySide6.QtGui import QColor

        return QColor(hex_str)
    except Exception:
        # Fallback: return None and let the item use its default colour.
        return None
