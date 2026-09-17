"""Chapter detection & selection panel — TOC extraction with editable end-pages.

Ports the Phase 3.2 logic from the original Tkinter ``convert_view``:
extract the PDF's table of contents, compute page ranges, and present each
chapter as a row with a checkbox, truncated title, start page (read-only),
and an editable end-page entry.  If any end-page is edited, manual segments
are generated and used for conversion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import icon
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.theme import theme_manager


class ChapterPanel(QWidget):
    """Detect TOC, list chapters with editable end-pages, emit selection."""

    # ── cross-thread signals ────────────────────────────────────────────
    _detect_done = Signal(list, int)    # (entries_with_range, total_pages)
    _detect_failed = Signal(str)        # error message
    selection_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._chapter_data: list[dict[str, Any]] = []
        self._input_file: Path | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # header row: button + hint
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self.detect_btn = QPushButton("  Detect chapters from TOC")
        self.detect_btn.setObjectName("Compact")
        self.detect_btn.setIcon(icon("scan", "#D4A574", 15))
        self.detect_btn.setCursor(Qt.PointingHandCursor)
        self.detect_btn.clicked.connect(self._on_detect)
        head.addWidget(self.detect_btn)
        head.addStretch()
        self.hint = QLabel("No chapters detected yet")
        self.hint.setObjectName("Caption")
        head.addWidget(self.hint)
        lay.addLayout(head)

        # scrollable chapter list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setMinimumHeight(90)
        self.scroll.setMaximumHeight(220)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            " QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(4)
        self.list_lay.addStretch()
        self.scroll.setWidget(self.list_host)
        lay.addWidget(self.scroll)

        # manual segments entry
        self.manual_entry = QLineEdit()
        self.manual_entry.setPlaceholderText(
            "Manual segments, e.g. 1-6, 7-12, 13-20  (optional)"
        )
        lay.addWidget(self.manual_entry)

        # wire cross-thread signals to main-thread slots
        self._detect_done.connect(self._populate)
        self._detect_failed.connect(self._on_detect_error)

        self._refresh_style()

    # ── public API ───────────────────────────────────────────────────────
    def set_input_file(self, path: Path | None) -> None:
        self._input_file = path
        self.detect_btn.setEnabled(path is not None and path.exists())

    def get_manual_segments(self) -> list[tuple[int, int]]:
        """Manual segments either from UI end-page edits or the entry field."""
        segs = self._build_manual_segments_from_edits()
        if segs:
            return segs
        text = self.manual_entry.text().strip()
        out: list[tuple[int, int]] = []
        if text:
            for part in text.split(","):
                part = part.strip()
                if "-" in part:
                    try:
                        s, e = part.split("-")
                        out.append((int(s.strip()), int(e.strip())))
                    except ValueError:
                        pass
        return [s for s in out if s[0] <= s[1]]

    def get_selected_chapters(self) -> list[str] | None:
        selected = [
            d["heading"] for d in self._chapter_data if d["var"].isChecked()
        ]
        return selected if selected else None

    def clear(self) -> None:
        self._chapter_data.clear()
        self._clear_rows()
        self.hint.setText("No chapters detected yet")

    # ── detection (runs in a worker thread) ──────────────────────────────
    def _on_detect(self) -> None:
        if not self._input_file or not self._input_file.exists():
            return
        self.detect_btn.setEnabled(False)
        self.hint.setText("Detecting…")
        SimpleWorker(self._run_detect).start()

    def _run_detect(self) -> None:
        try:
            from pypdf import PdfReader

            from core.pdf import TocExtractor

            reader = PdfReader(str(self._input_file))
            total_pages = len(reader.pages)
            toc = TocExtractor(log_callback=lambda *a: None).extract(
                self._input_file, None
            )
            if not toc:
                self._detect_failed.emit("No table of contents found in this PDF.")
                return

            entries: list[tuple[str, int, int]] = []
            for i, (heading, page) in enumerate(toc):
                start = page if 0 < page <= total_pages else 0
                if i + 1 < len(toc):
                    nxt = toc[i + 1][1]
                    end = nxt - 1 if nxt > start else total_pages
                else:
                    end = total_pages
                if start > end:
                    end = start
                entries.append((heading, start, end))

            self._detect_done.emit(entries, total_pages)
        except Exception as e:  # noqa: BLE001
            self._detect_failed.emit(str(e))

    # ── main-thread slots ────────────────────────────────────────────────
    def _populate(self, entries: list[tuple[str, int, int]], total_pages: int) -> None:
        self.detect_btn.setEnabled(True)
        self._chapter_data.clear()
        self._clear_rows()

        for idx, (heading, start, end) in enumerate(entries):
            row = QFrame()
            row.setObjectName("ChapterRow")
            row.setStyleSheet(self._row_style())
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(8)

            var = QCheckBox()
            var.setChecked(True)
            var.setCursor(Qt.PointingHandCursor)
            var.stateChanged.connect(self.selection_changed)

            title = QLabel(heading if len(heading) <= 48 else heading[:47] + "…")
            title.setStyleSheet(
                f"color: {theme_manager.palette.text_primary}; font-size: 12px;"
                " background: transparent;"
            )
            title.setToolTip(heading)

            start_lbl = QLabel(f"p.{start}" if start > 0 else "—")
            start_lbl.setStyleSheet(
                f"color: {theme_manager.palette.text_muted}; font-size: 11px;"
                " background: transparent;"
            )
            start_lbl.setMinimumWidth(36)

            end_entry = QLineEdit(str(end))
            end_entry.setMaximumWidth(54)
            end_entry.setAlignment(Qt.AlignCenter)
            end_entry.setStyleSheet(self._end_entry_style())
            end_entry.setToolTip("Edit the end page to adjust this chapter's boundary.")

            rl.addWidget(var)
            rl.addWidget(title, 1)
            rl.addWidget(start_lbl)
            rl.addWidget(QLabel("→"))
            rl.addWidget(end_entry)

            # insert before the trailing stretch
            self.list_lay.insertWidget(self.list_lay.count() - 1, row)

            self._chapter_data.append({
                "heading": heading,
                "start": start if start > 0 else 1,
                "end": end,
                "original_end": end,
                "var": var,
                "end_entry": end_entry,
                "row": row,
                "title": title,
            })

        self.hint.setText(
            f"{len(entries)} chapters detected · edit end-pages to adjust boundaries"
        )

    def _on_detect_error(self, msg: str) -> None:
        self.detect_btn.setEnabled(True)
        self.hint.setText(f"⚠ {msg}")

    # ── build manual segments from end-page edits ───────────────────────
    def _build_manual_segments_from_edits(self) -> list[tuple[int, int]]:
        if not self._chapter_data:
            return []
        modified = False
        ranges: list[tuple[int, int]] = []
        for d in self._chapter_data:
            try:
                txt = d["end_entry"].text().strip()
                cur = int(txt) if txt else d["end"]
            except ValueError:
                cur = d["end"]
            if cur != d["original_end"]:
                modified = True
                cur = max(d["start"], cur)
                d["end"] = cur
            ranges.append((d["start"], d["end"]))
        if not modified:
            return []
        ranges.sort(key=lambda x: x[0])
        fixed: list[tuple[int, int]] = []
        current = 0
        for s, e in ranges:
            if s <= current:
                s = current + 1
            if e < s:
                e = s
            fixed.append((s, e))
            current = e
        return fixed

    # ── helpers ──────────────────────────────────────────────────────────
    def _clear_rows(self) -> None:
        while self.list_lay.count() > 1:  # keep the trailing stretch
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _row_style(self) -> str:
        p = theme_manager.palette
        return (
            f"QFrame#ChapterRow {{ background-color: {p.bg_input};"
            f" border: 1px solid {p.border}; border-radius: 6px; }}"
        )

    def _end_entry_style(self) -> str:
        p = theme_manager.palette
        return (
            f"QLineEdit {{ background-color: {p.bg_surface};"
            f" color: {p.text_primary}; border: 1px solid {p.border};"
            f" border-radius: 5px; padding: 3px 4px; font-size: 11px; }}"
            f"QLineEdit:focus {{ border: 1px solid {p.accent}; }}"
        )

    def _refresh_style(self) -> None:
        p = theme_manager.palette
        self.manual_entry.setStyleSheet(
            f"QLineEdit {{ background-color: {p.bg_input}; color: {p.text_primary};"
            f" border: 1px solid {p.border}; border-radius: 8px; padding: 7px 10px; }}"
            f"QLineEdit:focus {{ border: 1px solid {p.accent}; }}"
        )

    def refresh_theme(self) -> None:
        self._refresh_style()
        for d in self._chapter_data:
            d["row"].setStyleSheet(self._row_style())
            d["end_entry"].setStyleSheet(self._end_entry_style())
            d["title"].setStyleSheet(
                f"color: {theme_manager.palette.text_primary}; font-size: 12px;"
                " background: transparent;"
            )
