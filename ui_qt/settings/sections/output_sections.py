"""V0.4.19 — the output settings sections.

``AiOutputSelectionSection`` and the seven ``Output*`` sections
(destination, generate, segmentation, keywords, postprocess, RAG, studio)
moved VERBATIM from ``ui_qt/settings/sections.py`` during the V0.4.19
de-monolithization — bodies byte-identical; only this docstring and the
re-homed imports are new.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.settings.widgets import (
    labeled_checkbox,
    labeled_combo,
    labeled_line,
    labeled_spin,
    make_form,
)


class AiOutputSelectionSection(QGroupBox):
    """What to include in summaries (executive/thorough/keypoints)."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output selection (what to include in summaries)", parent)
        self.controller = controller
        f = make_form()
        self.exec_cb = labeled_checkbox(
            "Executive summary  (150–200 words)",
            checked=controller.get_setting("summarisation.include_executive_summary", True),
        )
        self.thorough_cb = labeled_checkbox(
            "Thorough summary  (800–1200 words)",
            checked=controller.get_setting("summarisation.include_thorough_summary", True),
        )
        self.keypoints_cb = labeled_checkbox(
            "Keypoints  (bullet points)",
            checked=controller.get_setting("summarisation.include_keypoints", True),
        )
        f.addRow(self.exec_cb)
        f.addRow(self.thorough_cb)
        f.addRow(self.keypoints_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.include_executive_summary", self.exec_cb.isChecked())
        c.update_setting("summarisation.include_thorough_summary", self.thorough_cb.isChecked())
        c.update_setting("summarisation.include_keypoints", self.keypoints_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.exec_cb.setChecked(c.get_setting("summarisation.include_executive_summary", True))
        self.thorough_cb.setChecked(c.get_setting("summarisation.include_thorough_summary", True))
        self.keypoints_cb.setChecked(c.get_setting("summarisation.include_keypoints", True))


# ════════════════════════════════════════════════════════════════════════════
# Output sections
# ════════════════════════════════════════════════════════════════════════════


class OutputDestinationSection(QGroupBox):
    """Output-folder override + show-live-log + success-sound toggles."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output destination & interface", parent)
        self.controller = controller
        f = make_form()
        self.output_dir_edit = labeled_line(
            controller.get_setting("output.custom_dir", ""),
            placeholder="Leave blank to save next to the source document",
            tooltip="By default the output goes into the same folder as the input document.",
        )
        from PySide6.QtWidgets import QFileDialog

        dest_row = QHBoxLayout()
        dest_row.setContentsMargins(0, 0, 0, 0)
        dest_row.setSpacing(6)
        dest_row.addWidget(self.output_dir_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("Compact")
        browse_btn.clicked.connect(lambda: self._browse(QFileDialog))
        dest_row.addWidget(browse_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("Compact")
        clear_btn.clicked.connect(lambda: self.output_dir_edit.setText(""))
        dest_row.addWidget(clear_btn)
        f.addRow("Output folder", dest_row)
        self.show_log_cb = labeled_checkbox(
            "Show live log during conversion",
            checked=controller.get_setting("ui.show_live_log", False),
            tooltip="When off, only the brief status line above the progress bar is shown.",
        )
        f.addRow(self.show_log_cb)
        self.play_sound_cb = labeled_checkbox(
            "Play a success sound when conversion finishes",
            checked=controller.get_setting("ui.play_success_sound", True),
            tooltip="A gentle chime plays when a conversion completes successfully.",
        )
        f.addRow(self.play_sound_cb)
        self.setLayout(f)

    def _browse(self, QFileDialog) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose an output folder")
        if folder:
            self.output_dir_edit.setText(folder)

    def save(self) -> None:
        c = self.controller
        c.update_setting("output.custom_dir", self.output_dir_edit.text().strip())
        c.update_setting("ui.show_live_log", self.show_log_cb.isChecked())
        c.update_setting("ui.play_success_sound", self.play_sound_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.output_dir_edit.setText(c.get_setting("output.custom_dir", ""))
        self.show_log_cb.setChecked(c.get_setting("ui.show_live_log", False))
        self.play_sound_cb.setChecked(c.get_setting("ui.play_success_sound", True))


class OutputGenerateSection(QGroupBox):
    """Generate summaries/DOCX/author/TOC."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Generate", parent)
        self.controller = controller
        f = make_form()
        self.summaries_cb = labeled_checkbox(
            "Generate chapter summaries",
            checked=controller.get_setting("summarisation.enabled", False),
        )
        self.docx_cb = labeled_checkbox(
            "Generate DOCX report",
            checked=controller.get_setting("docx.enabled", False),
        )
        self.author_edit = labeled_line(
            controller.get_setting("docx.author", "Elixir"),
            placeholder="Author name for the DOCX metadata",
        )
        self.toc_cb = labeled_checkbox(
            "Include table of contents in DOCX",
            checked=controller.get_setting("docx.include_toc", True),
        )
        f.addRow(self.summaries_cb)
        f.addRow(self.docx_cb)
        f.addRow("DOCX author", self.author_edit)
        f.addRow(self.toc_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.enabled", self.summaries_cb.isChecked())
        c.update_setting("docx.enabled", self.docx_cb.isChecked())
        c.update_setting("docx.author", self.author_edit.text().strip())
        c.update_setting("docx.include_toc", self.toc_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.summaries_cb.setChecked(c.get_setting("summarisation.enabled", False))
        self.docx_cb.setChecked(c.get_setting("docx.enabled", False))
        self.author_edit.setText(c.get_setting("docx.author", "Elixir"))
        self.toc_cb.setChecked(c.get_setting("docx.include_toc", True))


class OutputSegmentationSection(QGroupBox):
    """Strategy + token limit + page-group + keywords."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Segmentation", parent)
        self.controller = controller
        f = make_form()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["auto", "heading", "semantic", "token"])
        self.strategy_combo.setCurrentText(controller.get_setting("segmentation.strategy", "auto"))
        self.strategy_combo.setToolTip(
            "auto: Chapter-Level → TOC → Heading → Semantic → Token (recommended)\n"
            "heading: Split at markdown headings (#, ##)\n"
            "semantic: Split by semantic similarity (LLM-based)\n"
            "token: Split at fixed token intervals (last resort)"
        )
        f.addRow("Strategy", self.strategy_combo)

        # V13.35.0: Strategy description (updates on selection change)
        _STRAT_DESC = {
            "auto": "Automatically selects the best strategy: Chapter-Level (if the PDF has outlines) → TOC → Heading → Semantic → Token. Recommended for most books.",
            "heading": "Splits at markdown headings (#, ##). Best for well-structured documents with a clear heading hierarchy.",
            "semantic": "Splits by semantic similarity between paragraphs using LLM-based boundary detection. Best for unstructured text without clear headings. Slower.",
            "token": "Splits at fixed token intervals. Guarantees segments fit the context window but may break mid-topic. Use as a last resort.",
        }
        self.strat_desc_label = QLabel(_STRAT_DESC.get(self.strategy_combo.currentText(), ""))
        self.strat_desc_label.setWordWrap(True)
        self.strat_desc_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        f.addRow("", self.strat_desc_label)
        self.strategy_combo.currentTextChanged.connect(
            lambda txt: self.strat_desc_label.setText(_STRAT_DESC.get(txt, ""))
        )

        self.token_spin = labeled_spin(
            int(
                controller.get_setting("segmentation.token_limit", 2000)
            ),  # V13.35.0: 1200 → 2000 (matches settings.py default)
            minimum=500,
            maximum=32000,
            tooltip=(
                "Maximum tokens per segment.\n"
                "• Smaller values (500-1500): more LLM calls, but each segment fits comfortably in the context window.\n"
                "• Larger values (2000-8000): fewer calls, but risk of truncation on long chapters.\n"
                "• Default 2000 works for most models with 32k context.\n"
                "• For Gemma 4 12B (32k context, ~10.9 GB VRAM), 1500-2000 is optimal."
            ),
        )
        f.addRow("Token limit / segment", self.token_spin)
        self.page_group_spin = labeled_spin(
            int(controller.get_setting("segmentation.page_group_size", 10)),
            minimum=1,
            maximum=100,
        )
        f.addRow("Page-group size", self.page_group_spin)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("segmentation.strategy", self.strategy_combo.currentText())
        c.update_setting("segmentation.token_limit", self.token_spin.value())
        c.update_setting("segmentation.page_group_size", self.page_group_spin.value())

    def reload(self) -> None:
        c = self.controller
        self.strategy_combo.setCurrentText(c.get_setting("segmentation.strategy", "auto"))
        self.token_spin.setValue(
            int(c.get_setting("segmentation.token_limit", 2000))
        )  # V13.35.0: 1200 → 2000
        self.page_group_spin.setValue(int(c.get_setting("segmentation.page_group_size", 10)))


class OutputKeywordsSection(QGroupBox):
    """Custom chapter keywords — loaded from / saved to an editable MD file.

    V4.3.0: Replaces the old inline QTextEdit with a file-based editor.
    The keywords live in ``config/chapter_keywords.md`` (shipped with the
    app, user-editable in any text editor). The section shows the file
    path, a read-only preview, and "Edit file" / "Reload" buttons.

    On ``save()``, the MD file is parsed (one keyword per non-comment line)
    and the resulting list is written to ``segmentation.custom_keywords``
    so the segmenter can use it. On ``reload()``, the preview is refreshed
    from the file.
    """

    # The shipped default file, relative to the project root.
    _DEFAULT_KEYWORDS_FILE = "config/chapter_keywords.md"

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Custom chapter keywords", parent)
        self.controller = controller
        layout = QVBoxLayout(self)

        # Resolve the keywords file path. Stored in settings so the user
        # can point to a custom file; defaults to the shipped one.
        import sys
        from pathlib import Path

        if getattr(sys, "frozen", False):
            # PACKAGING: the shipped default inside the install folder is
            # READ-ONLY. Copy it once to the user-data dir (the copy the
            # user actually edits); never write inside the install folder.
            import shutil

            from utils.settings import user_data_dir

            default_path = user_data_dir() / "config" / "chapter_keywords.md"
            if not default_path.exists():
                default_path.parent.mkdir(parents=True, exist_ok=True)
                from app_paths import resource_path

                bundled = resource_path("config") / "chapter_keywords.md"
                if bundled.exists():
                    shutil.copy2(bundled, default_path)
                else:
                    self._write_default_file(default_path)
        else:
            project_root = Path(__file__).resolve().parents[3]
            default_path = project_root / self._DEFAULT_KEYWORDS_FILE
        stored = controller.get_setting("segmentation.keywords_file", "")
        self._keywords_file = Path(stored) if stored else default_path

        # If the default file doesn't exist (e.g. running from a different
        # cwd), fall back to creating it from the in-app default.
        if not self._keywords_file.exists() and self._keywords_file == default_path:
            self._write_default_file(default_path)

        # File path row + edit/reload buttons
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_label = QLabel(str(self._keywords_file))
        self.path_label.setObjectName("Caption")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)

        self.edit_btn = QPushButton("Edit file")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setToolTip("Open the keywords file in your default text editor.")
        self.edit_btn.clicked.connect(self._on_edit_file)
        path_row.addWidget(self.edit_btn)

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setCursor(Qt.PointingHandCursor)
        self.reload_btn.setToolTip("Re-read the keywords file and update the preview.")
        self.reload_btn.clicked.connect(self._on_reload_file)
        path_row.addWidget(self.reload_btn)
        layout.addLayout(path_row)

        # Read-only preview of the parsed keywords
        self.preview_label = QLabel()
        self.preview_label.setObjectName("Caption")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(
            "font-size: 11px; padding: 8px; background: rgba(0,0,0,0.03);border-radius: 4px;"
        )
        layout.addWidget(self.preview_label)

        hint = QLabel(
            "Keywords are loaded from the MD file above. Edit the file to "
            "add/remove keywords (one per line; lines starting with # are "
            "comments). Used by the heading strategy to detect chapter "
            "boundaries in scanned PDFs."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._refresh_preview()

    def _parse_keywords_file(self) -> list:
        """Parse the MD file → list of keyword strings."""
        if not self._keywords_file.exists():
            return ["فصل", "بخش", "Chapter", "Part"]
        kws = []
        for line in self._keywords_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # Skip comments, blank lines, and markdown blockquotes (> ...)
            if not line or line.startswith("#") or line.startswith(">"):
                continue
            kws.append(line)
        return kws

    def _refresh_preview(self) -> None:
        kws = self._parse_keywords_file()
        count = len(kws)
        preview = ", ".join(kws[:20])
        if count > 20:
            preview += f" … (+{count - 20} more)"
        self.preview_label.setText(f"{count} keywords loaded: {preview}")

    def _on_edit_file(self) -> None:
        """Open the keywords file in the OS default text editor."""
        import os
        import subprocess
        import sys

        path = str(self._keywords_file)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:
            pass  # best-effort (UI — never crash)

    def _on_reload_file(self) -> None:
        self._refresh_preview()

    @staticmethod
    def _write_default_file(path) -> None:
        """Write the shipped default keywords if the file is missing."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Chapter Heading Keywords\n\n"
            "# English\nChapter\nPart\nSection\nUnit\nLesson\nModule\n"
            "Appendix\nIntroduction\nPreface\nPrologue\nEpilogue\n\n"
            "# Persian\nفصل\nبخش\nقسمت\nدرس\nمبحث\nباب\nمقدمه\nپیوست\n",
            encoding="utf-8",
        )

    def save(self) -> None:
        kws = self._parse_keywords_file()
        self.controller.update_setting("segmentation.custom_keywords", kws)
        self.controller.update_setting("segmentation.keywords_file", str(self._keywords_file))

    def reload(self) -> None:
        from pathlib import Path

        stored = self.controller.get_setting("segmentation.keywords_file", "")
        if stored:
            self._keywords_file = Path(stored)
        self.path_label.setText(str(self._keywords_file))
        self._refresh_preview()


class OutputPostprocessSection(QGroupBox):
    """Markdown post-processing toggles."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Markdown post-processing", parent)
        self.controller = controller
        f = make_form()
        self.clean_cb = labeled_checkbox(
            "Clean Markdown (whitespace, headings)",
            checked=controller.get_setting("postprocess.clean_markdown", True),
        )
        self.spaces_cb = labeled_checkbox(
            "Fix missing spaces between words",
            checked=controller.get_setting("postprocess.fix_missing_spaces", False),
        )
        self.pagehead_cb = labeled_checkbox(
            "Remove page-number headings",
            checked=controller.get_setting("postprocess.remove_page_number_headings", True),
        )
        self.separators_cb = labeled_checkbox(
            "Convert separators to HTML comments",
            checked=controller.get_setting("postprocess.convert_separators_to_comments", False),
        )
        self.tokensaver_cb = labeled_checkbox(
            "Token saver (trim very long pages)",
            checked=controller.get_setting("postprocess.token_saver", True),
        )
        f.addRow(self.clean_cb)
        f.addRow(self.spaces_cb)
        f.addRow(self.pagehead_cb)
        f.addRow(self.separators_cb)
        f.addRow(self.tokensaver_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("postprocess.clean_markdown", self.clean_cb.isChecked())
        c.update_setting("postprocess.fix_missing_spaces", self.spaces_cb.isChecked())
        c.update_setting("postprocess.remove_page_number_headings", self.pagehead_cb.isChecked())
        c.update_setting(
            "postprocess.convert_separators_to_comments", self.separators_cb.isChecked()
        )
        c.update_setting("postprocess.token_saver", self.tokensaver_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.clean_cb.setChecked(c.get_setting("postprocess.clean_markdown", True))
        self.spaces_cb.setChecked(c.get_setting("postprocess.fix_missing_spaces", False))
        self.pagehead_cb.setChecked(c.get_setting("postprocess.remove_page_number_headings", True))
        self.separators_cb.setChecked(
            c.get_setting("postprocess.convert_separators_to_comments", False)
        )
        self.tokensaver_cb.setChecked(c.get_setting("postprocess.token_saver", True))


class OutputRagSection(QGroupBox):
    """RAG frontmatter + target format."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("RAG output", parent)
        self.controller = controller
        f = make_form()
        self.frontmatter_cb = labeled_checkbox(
            "Include YAML frontmatter per chapter",
            checked=controller.get_setting("rag.include_frontmatter", True),
        )
        self.target_combo = labeled_combo(
            ["chromadb", "notebooklm", "plain"],
            controller.get_setting("rag.target_format", "chromadb"),
        )
        f.addRow(self.frontmatter_cb)
        f.addRow("Target format", self.target_combo)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("rag.include_frontmatter", self.frontmatter_cb.isChecked())
        c.update_setting("rag.target_format", self.target_combo.currentText())

    def reload(self) -> None:
        c = self.controller
        self.frontmatter_cb.setChecked(c.get_setting("rag.include_frontmatter", True))
        idx = self.target_combo.findText(c.get_setting("rag.target_format", "chromadb"))
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)


class OutputStudioSection(QGroupBox):
    """V4.1.0: Output Studio — toggle which extra output types to generate.

    Replaces the old ``OutputComingSoonSection`` (V4.0.0 disabled stubs).
    Each checkbox maps to a ``outputs.<name>`` setting and, through
    ``Controller.build_request_from_ui``, to the matching ``output_*`` flag
    on ``ConversionRequest``. The converter only invokes a generator when its
    flag is enabled, so unchecking an output skips its LLM call entirely.

    V10.29.0 (Sprint 2.2): The output list is now imported from
    ``core.outputs.registry`` — the single source of truth.  Previously
    this section hardcoded 9 outputs and silently missed evidence_map +
    the 5 V10.20.0/V10.21.0 outputs.
    """

    # V10.29.0: import from the registry so this list can never drift
    # from the wizard / dialog / controller again.
    from core.outputs.registry import get_settings_section_outputs as _get_outputs

    _OUTPUTS = _get_outputs()

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output Studio", parent)
        self.controller = controller
        f = make_form()

        self._checkboxes: dict = {}
        for key, label, default in self._OUTPUTS:
            checked = controller.get_setting(key, default)
            cb = labeled_checkbox(label, checked=checked)
            self._checkboxes[key] = (cb, default)
            f.addRow(cb)

        hint = QLabel(
            "Each enabled output adds files to the output folder after the "
            "simplified keypoints. Disable any you don't need to skip its LLM "
            "call. The Mind Map is fully deterministic (no LLM, instant)."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        for key, (cb, _default) in self._checkboxes.items():
            c.update_setting(key, cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        for key, (cb, default) in self._checkboxes.items():
            cb.setChecked(c.get_setting(key, default))
