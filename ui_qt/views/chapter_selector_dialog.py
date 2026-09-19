"""Modal scrollable chapter selector.

Replaces the inline ChapterPanel that lived inside the "Optional" collapsible.
The user checks "Select specific chapters…" on the home screen → this modal
opens with a scrollable list of detected chapters (each with a checkbox +
page range).  Selections are returned to the caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import icon
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.theme import theme_manager


class ChapterSelectorDialog(QDialog):
    """Modal TOC selector — detect chapters, list them scrollably, return picks."""

    _detect_done = Signal(list, int)  # (entries, total_pages)
    _detect_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None, output_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select chapters")
        self.resize(500, 500)  # V7.4.0: was 560x560 — compact
        self._input_file: Path | None = None
        self._chapter_data: list[dict[str, Any]] = []
        # V0.02: metadata-children bookmarks hidden from the list (hint text)
        self._hidden_metadata_count: int = 0
        # V7.7.0: output dir for resume detection (which chapters are already done)
        self._output_dir = output_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        # ── header row: detect button + hint ─────────────────────────────
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self.detect_btn = QPushButton("  Detect chapters from TOC")
        self.detect_btn.setIcon(icon("scan", "#B8915A", 15))
        self.detect_btn.clicked.connect(self._on_detect)
        head.addWidget(self.detect_btn)
        head.addStretch()
        self.hint = QLabel("No file loaded")
        self.hint.setObjectName("Caption")
        head.addWidget(self.hint)
        root.addLayout(head)

        # ── scrollable chapter list ──────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
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
        root.addWidget(self.scroll, 1)

        # ── select-all / none + filter toggles row ──────────────────────
        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 0, 0, 0)
        sel_row.setSpacing(8)
        self.select_all_btn = QPushButton("Select all")
        self.select_all_btn.setObjectName("Compact")
        self.select_all_btn.clicked.connect(lambda: self._set_all(True))
        self.select_none_btn = QPushButton("Select none")
        self.select_none_btn.setObjectName("Compact")
        self.select_none_btn.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(self.select_all_btn)
        sel_row.addWidget(self.select_none_btn)
        sel_row.addStretch()

        # Toggle: Main chapters only (deselects front/back matter)
        self.main_chapters_btn = QPushButton("Main chapters only")
        self.main_chapters_btn.setObjectName("Compact")
        self.main_chapters_btn.setToolTip(
            "Select only main chapters ( deselects front matter, about author, copyright, etc.)"
        )
        self.main_chapters_btn.clicked.connect(self._select_main_chapters)
        sel_row.addWidget(self.main_chapters_btn)

        # Toggle: Additional parts only (selects only front/back matter)
        self.additional_parts_btn = QPushButton("Additional parts only")
        self.additional_parts_btn.setObjectName("Compact")
        self.additional_parts_btn.setToolTip(
            "Select only front/back matter (dedication, about author, copyright, etc.)"
        )
        self.additional_parts_btn.clicked.connect(self._select_additional_parts)
        sel_row.addWidget(self.additional_parts_btn)
        root.addLayout(sel_row)

        # ── buttons ──────────────────────────────────────────────────────
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setObjectName("Primary")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self._detect_done.connect(self._populate)
        self._detect_failed.connect(self._on_detect_error)

    # ── public API ───────────────────────────────────────────────────────
    def set_input_file(self, path: Path | None) -> None:
        self._input_file = path
        self.detect_btn.setEnabled(path is not None and path.exists())
        if path and path.exists():
            self.hint.setText("Auto-detecting chapters…")
            # Auto-trigger detection immediately — no manual click needed
            self._on_detect()
        else:
            self.hint.setText("No file loaded")

    def get_selected_chapters(self) -> list[str] | None:
        selected = [d["heading"] for d in self._chapter_data if d["var"].isChecked()]
        return selected if selected else None

    def get_selected_page_ranges(self) -> list[tuple[int, int]] | None:
        """Return (start, end) page ranges for selected chapters.
        Used to skip OCR/extraction of unselected pages."""
        ranges = []
        for d in self._chapter_data:
            if d["var"].isChecked():
                start = d.get("start", 0)
                end = d.get("end", 0)
                if start > 0 and end > 0:
                    ranges.append((start, end))
        return ranges if ranges else None

    def has_chapters(self) -> bool:
        return bool(self._chapter_data)

    # ── detection (worker thread) ────────────────────────────────────────
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
            total = len(reader.pages)
            toc = TocExtractor(log_callback=lambda *a: None).extract(self._input_file, None)
            if not toc:
                self._detect_failed.emit("No table of contents found in this PDF.")
                return

            # V0.02 (false-success RCA): drop "metadata children" outline
            # levels BEFORE listing — the SAME rule the segmenter's Layer 1
            # applies (single source: compute_metadata_child_levels). For
            # "97 Things" this hides the 97 per-chapter AUTHOR bookmarks:
            # they were listed as selectable "chapters", users picked them
            # alongside the real titles, and the polluted selection could
            # end up summarizing nothing while the pipeline reported
            # success. Also fixes the page ranges: a title whose next
            # (child) bookmark shares its start page previously showed as
            # spanning to the END OF THE BOOK (end = total).
            from core.segmentation.segmenter import compute_metadata_child_levels

            _by_level: dict[int, list] = {}
            for e in toc:
                _p = e[1] if isinstance(e, (tuple, list)) else getattr(e, "page", None)
                if _p is None or _p <= 0:
                    continue
                _lvl = (
                    e[2]
                    if (isinstance(e, (tuple, list)) and len(e) > 2)
                    else getattr(e, "level", 0)
                )
                _h = e[0] if isinstance(e, (tuple, list)) else getattr(e, "title", "")
                _by_level.setdefault(_lvl, []).append((_h, _p))
            _excluded = compute_metadata_child_levels(_by_level)
            _hidden = 0
            if _excluded:
                _excluded_levels = set(_excluded)
                _before = len(toc)
                toc = [
                    e
                    for e in toc
                    if (
                        e[2]
                        if (isinstance(e, (tuple, list)) and len(e) > 2)
                        else getattr(e, "level", 0)
                    )
                    not in _excluded_levels
                ]
                _hidden = _before - len(toc)

            entries: list[tuple[str, int, int]] = []
            for i, (heading, page) in enumerate(toc):
                start = page if 0 < page <= total else 0
                if i + 1 < len(toc):
                    nxt = toc[i + 1][1]
                    # V0.02: same-page (or out-of-order) neighbour → this
                    # chapter occupies just its start page — NOT the rest of
                    # the book (was: end = total).
                    end = nxt - 1 if nxt > start else start
                else:
                    end = total
                if start > end:
                    end = start
                entries.append((heading, start, end))
            # stash the hidden count for _populate's hint BEFORE the emit
            # (queued signal — the slot runs on the main thread afterwards)
            self._hidden_metadata_count = _hidden
            self._detect_done.emit(entries, total)
        except Exception as e:  # noqa: BLE001
            self._detect_failed.emit(str(e))

    # ── main-thread slots ────────────────────────────────────────────────
    def _populate(self, entries: list[tuple[str, int, int]], total_pages: int) -> None:
        self.detect_btn.setEnabled(True)
        self._chapter_data.clear()
        self._clear_rows()
        p = theme_manager.palette

        # V7.7.0: detect which chapters already have valid summaries (resume)
        processed_headings = set()
        if self._output_dir:
            try:
                from core.pipeline.chapter_resume import (
                    _sanitize_heading,
                    detect_processed_chapters,
                )

                processed = detect_processed_chapters(self._output_dir)
                processed_headings = set(processed.keys())
            except Exception:
                pass  # best-effort (UI — never crash)
        done_count = 0

        for _idx, (heading, start, end) in enumerate(entries):
            # V10.2.5: Hierarchical indentation based on chapter number depth.
            # "1" → level 0 (no indent), "2.1" → level 1 (1 indent),
            # "2.1.1" → level 2 (2 indents), etc.
            import re as _re

            _num_match = _re.match(r"^(\d+(?:\.\d+)*)\s", heading)
            _indent_level = 0
            if _num_match:
                _indent_level = _num_match.group(1).count(".")
            _indent_px = _indent_level * 20  # 20px per level

            row = QFrame()
            row.setObjectName("ChapterRow")
            row.setStyleSheet(
                f"QFrame#ChapterRow {{ background-color: {p.bg_input};"
                f" border: 1px solid {p.border}; border-radius: 6px;"
                f" margin-left: {_indent_px}px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 5, 8, 5)
            rl.setSpacing(8)
            var = QCheckBox()
            var.setChecked(True)
            var.setCursor(Qt.PointingHandCursor)
            # V10.2.5: bold main chapters, normal sub-chapters
            _is_main = _indent_level == 0
            _font_weight = "font-weight: 600;" if _is_main else "font-weight: 400;"
            _prefix = ""
            if _indent_level > 0:
                _prefix = "  " * _indent_level + "↳ "
            title = QLabel(_prefix + (heading if len(heading) <= 60 else heading[:59] + "…"))
            title.setStyleSheet(
                f"color: {p.text_primary}; font-size: 12px; {_font_weight} background: transparent;"
            )
            title.setToolTip(heading)
            pages = QLabel(f"p.{start}–{end}" if start > 0 else "—")
            pages.setStyleSheet(f"color: {p.text_muted}; font-size: 11px; background: transparent;")
            rl.addWidget(var)
            rl.addWidget(title, 1)
            rl.addWidget(pages)

            # V7.7.0: "done" badge if this chapter has an existing summary
            heading_key = _sanitize_heading(heading).lower()
            if heading_key in processed_headings:
                done_badge = QLabel("✓ done")
                done_badge.setStyleSheet(
                    f"font-size: 10px; font-weight: 600; color: {p.success};"
                    f" background: transparent; padding: 2px 6px;"
                )
                done_badge.setToolTip(
                    "Already summarized in a previous run — will be skipped if Resume mode is on"
                )
                rl.addWidget(done_badge)
                done_count += 1

            self.list_lay.insertWidget(self.list_lay.count() - 1, row)
            self._chapter_data.append({"heading": heading, "var": var, "row": row})

        hint_text = f"{len(entries)} chapters detected · {total_pages} pages"
        _hidden = getattr(self, "_hidden_metadata_count", 0)
        if _hidden > 0:
            hint_text += f" · {_hidden} author/annotation bookmark(s) hidden"
        if done_count > 0:
            hint_text += f" · {done_count} already done (will skip if Resume on)"
        self.hint.setText(hint_text)

    def _on_detect_error(self, msg: str) -> None:
        self.detect_btn.setEnabled(True)
        self.hint.setText(f"⚠ {msg}")

    def _clear_rows(self) -> None:
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_all(self, checked: bool) -> None:
        for d in self._chapter_data:
            d["var"].setChecked(checked)

    # ── Patterns that indicate front/back matter (not main chapters) ────
    _FRONT_BACK_MATTER = {
        "title page",
        "dedication",
        "epigraph",
        "contents",
        "table of contents",
        "acknowledgments",
        "acknowledgements",
        "about the author",
        "about the publisher",
        "copyright",
        "colophon",
        "glossary",
        "index",
        "references",
        "bibliography",
        "preface",
        "foreword",
        "prologue",
        "epilogue",
        "author's note",
        "authors note",
        "front cover",
        "back cover",
        "praise",
        "reviews",
        "other books",
    }

    def _is_front_back_matter(self, heading: str) -> bool:
        h = heading.strip().lower()
        return any(fm in h for fm in self._FRONT_BACK_MATTER)

    def _select_main_chapters(self) -> None:
        """Select only main chapters; deselect front/back matter."""
        for d in self._chapter_data:
            is_fm = self._is_front_back_matter(d["heading"])
            d["var"].setChecked(not is_fm)

    def _select_additional_parts(self) -> None:
        """Select only front/back matter; deselect main chapters."""
        for d in self._chapter_data:
            is_fm = self._is_front_back_matter(d["heading"])
            d["var"].setChecked(is_fm)
