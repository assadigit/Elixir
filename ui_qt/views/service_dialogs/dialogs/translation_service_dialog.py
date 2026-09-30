"""Translation Service dialog (V18.20.4.6, P5 / O-b2 split).

TranslationServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ; it subclasses the shared
BaseServiceDialog. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    _show_success_modal,
)

logger = logging.getLogger(__name__)


class TranslationServiceDialog(BaseServiceDialog):
    """V11.29: Clean, minimal Translation dialog.

    UI layout (top to bottom):
      +--------------------------------------------------------+
      | Translation Service                                    |
      | [Paste Text] [Pick File]   <- tabs (Pick File          |
      |                              hidden; queue is the       |
      |                              file picker)               |
      | Model:  [translategemma-4b-... v] [Refresh] [gear]     |
      | Direction:  EN → FA  (auto-detected)                  |
      | Format:  [Markdown (.md) v]                            |
      | File queue:                       [Add Files...] [Remove] |
      |   - /path/to/tiger.md                                  |
      |   - /path/to/lion.md                                   |
      |   - ...                                                |
      | Save to:  /path/to/tiger-fa-translation.md  [Browse...]  |
      | [progress bar]                                         |
      | status message                                         |
      | [Cancel] [Try Another File] [Process]                  |
      +--------------------------------------------------------+

    gear Settings pop-up (Mode + Obsidian + save-to folder):
      +--------------------------------------------+
      | Translation Settings                       |
      | Translation mode:                          |
      |   [Literal v]                              |
      | [x] Obsidian-style markdown                |
      | Default save-to folder:                    |
      |   [____________________] [Browse...]       |
      | [Cancel]                          [OK]     |
      +--------------------------------------------+

    Behaviour:
      - **Auto-detected direction** - no Direction dropdown. The
        ``TranslationEngine.auto_detect_direction(text)`` reads the input
        (paste text or first queued file) and shows "EN → FA" as a
        read-only label.
      - **Unified file picker** - the "Pick File" tab is hidden; the
        visible file queue *is* the file picker. Picking files (via the
        queue's "Add Files..." button) enqueues them. If the queue is empty,
        the paste-text flow is used; if the queue has files, every file
        is translated and saved as ``{stem}-{lang}-translation{ext}``.
      - **Live model refresh** - ``_refresh_models()`` runs in
        ``showEvent`` so the model dropdown always reflects what's
        actually installed in Ollama (not a stale settings value).
      - **Auto-filled output path** - when a file is enqueued, the output
        path auto-fills with
        ``{source_dir}/{stem}-{lang}-translation{ext}``; in paste mode,
        ``{default_dir}/pasted-{lang}-translation{ext}``.
      - **gear** - opens a modal pop-up with Mode (literal/simplified),
        Obsidian checkbox, and a default save-to folder setting.
      - **TranslationEngine** (``core.translation.translation_engine``)
        does all the actual translation; the dialog just wires UI ->
        engine + ``write_output`` for saving.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(
            controller, "🌐 Translation Service", parent, accept_files=True, accept_text=True
        )
        # V11.29: Resolved attrs - set here (after super().__init__, which
        # built the widgets). These are NOT widget refs, so overwriting them
        # is safe. They're read by _process (background thread) + _save_result
        # (main thread) without touching Qt widgets.
        self._resolved_format: str = ".md"
        self._resolved_obsidian: bool = False
        self._resolved_model: str = "translategemma-12b-it.Q4_K_M_mradermacher:latest"
        self._resolved_mode: str = "literal"  # literal | simplified
        self._resolved_source_lang: str = "en"
        self._resolved_target_lang: str = "fa"
        self._detected_direction: tuple[str, str] = ("en", "fa")
        # V11.29: gear-icon "save-to" setting (persisted). Empty = use the
        # source file's directory.
        self._save_to_folder: str = self._get_setting("save_to_folder", "") or ""
        # V11.29: don't refresh models more than once per show.
        self._models_refreshed_on_show: bool = False
        self._start_time = None

    # ----------------------------------------------------------------
    # UI construction
    # ----------------------------------------------------------------
    def _build_options(self, layout: QVBoxLayout) -> None:
        """Build the translation-specific options row.

        The base class's ``_build_ui`` already created the Paste Text /
        Pick File tabs. Here we hide the Pick File tab (the queue is now
        the file picker) and add our options below the tabs.
        """
        from PySide6.QtWidgets import (
            QListWidget as _QLW,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )

        # V11.29: Hide the Pick File tab. The file queue below is the
        # single source of truth for "which files to translate". This
        # unifies the picker + queue (req. #8).
        if hasattr(self, "tabs") and self.tabs is not None and self.tabs.count() > 1:
            self.tabs.setTabVisible(1, False)
            self.tabs.setCurrentIndex(0)  # stay on the Paste Text tab

        # -- Row 1: Format + gear Settings (top-right) --------------
        # V11.29.1: model picker moved to gear settings. Direction label
        # removed (auto-detected silently). Gear icon at top-right.
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.addWidget(QLabel("Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItem("Markdown (.md)", ".md")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.setCurrentIndex(0)
        self.fmt_combo.currentIndexChanged.connect(self._refresh_default_output)
        top_row.addWidget(self.fmt_combo)
        top_row.addStretch()
        # Gear button — top-right corner.
        self.gear_btn = _QPB("⚙ Settings")
        self.gear_btn.setToolTip(
            "Translation settings: model, mode (literal/simplified), "
            "Obsidian markdown, default save-to folder."
        )
        self.gear_btn.clicked.connect(self._open_settings)
        top_row.addWidget(self.gear_btn)
        layout.addLayout(top_row)

        # V11.29.1: model combo is created here (populated in _refresh_models)
        # but NOT shown on the main UI — it's in the gear settings dialog.
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(280)

        # (Row 2 was the old format dropdown — now merged into Row 1 above.)

        # -- Row 3: Unified file queue (= file picker) --------------
        queue_row = QHBoxLayout()
        queue_row.setSpacing(6)
        queue_lbl = QLabel("File queue:")
        queue_lbl.setObjectName("Caption")
        queue_row.addWidget(queue_lbl)
        queue_row.addStretch()
        self._file_queue: list[str] = []
        self.file_queue_list = _QLW()
        self.file_queue_list.setMinimumHeight(60)
        self.file_queue_list.setMaximumHeight(120)
        self.file_queue_list.setToolTip(
            "Files queued for translation. Use 'Add Files...' to enqueue "
            "one or more files. When the queue is non-empty, every file "
            "is translated and saved as {stem}-{lang}-translation{ext}; "
            "when empty, the paste-text tab content is translated."
        )
        self.file_queue_list.itemSelectionChanged.connect(self._refresh_default_output)
        add_files_btn = _QPB("Add Files...")
        add_files_btn.setToolTip("Pick one or more files to enqueue.")
        add_files_btn.clicked.connect(self._add_translation_files)
        rm_file_btn = _QPB("Remove")
        rm_file_btn.setToolTip("Remove the selected file from the queue.")
        rm_file_btn.clicked.connect(self._remove_translation_file)
        clear_queue_btn = _QPB("Clear")
        clear_queue_btn.setToolTip("Clear the entire queue.")
        clear_queue_btn.clicked.connect(self._clear_queue)
        queue_btns = QVBoxLayout()
        queue_btns.setSpacing(4)
        queue_btns.addWidget(add_files_btn)
        queue_btns.addWidget(rm_file_btn)
        queue_btns.addWidget(clear_queue_btn)
        queue_btns.addStretch()
        queue_row.addWidget(self.file_queue_list, 1)
        queue_row.addLayout(queue_btns)
        layout.addLayout(queue_row)

        # V11.29: Wire paste-text changes -> auto-detect direction +
        # auto-fill the output path.
        if hasattr(self, "text_input") and self.text_input is not None:
            self.text_input.textChanged.connect(self._update_direction)

        # Pre-fill the default output path for paste mode.
        self._refresh_default_output()

    # ----------------------------------------------------------------
    # Show event - live-refresh models from Ollama
    # ----------------------------------------------------------------
    def showEvent(self, event) -> None:
        """V11.29: On first show, refresh the model list from Ollama so
        the dropdown reflects what's actually installed (not a stale
        settings value).
        """
        super().showEvent(event)
        if not getattr(self, "_models_refreshed_on_show", False):
            try:
                self._refresh_models()
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
            self._models_refreshed_on_show = True

    # ----------------------------------------------------------------
    # Direction auto-detection
    # ----------------------------------------------------------------
    def _update_direction(self) -> None:
        """V11.29: Auto-detect the translation direction from the current
        input text and update the read-only direction label.

        Reads (in priority order):
          1. The paste-text tab content (if the user has typed something).
          2. The first queued file's content (truncated for speed).
          3. The first file_path_edit file's content (legacy fallback).

        Falls back to "EN → FA" if no text is available.
        """
        from core.translation.translation_engine import TranslationEngine

        text = self._peek_input_text()
        if text and text.strip():
            try:
                self._detected_direction = TranslationEngine.auto_detect_direction(text)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
        src, tgt = self._detected_direction
        src_lbl = "EN" if src == "en" else "FA"
        tgt_lbl = "EN" if tgt == "en" else "FA"
        if hasattr(self, "direction_lbl") and self.direction_lbl is not None:
            self.direction_lbl.setText(f"{src_lbl} -> {tgt_lbl}  (auto-detected)")
        # The default output filename contains the target lang, so re-eval.
        self._refresh_default_output()

    def _peek_input_text(self) -> str:
        """V11.29: Get a *sample* of the current input for direction
        detection. Reads at most 5 000 chars (enough for detection, fast).

        Order: paste-text -> first queued file -> file_path_edit file.
        Returns "" if nothing is available.
        """
        try:
            # 1. Paste-text tab.
            if hasattr(self, "text_input") and self.text_input is not None:
                txt = self.text_input.toPlainText()
                if txt and txt.strip():
                    return txt[:5000]
            # 2. First queued file.
            queue = getattr(self, "_file_queue", None) or []
            if queue:
                p = Path(queue[0])
                if p.exists():
                    return p.read_text(encoding="utf-8", errors="replace")[:5000]
            # 3. file_path_edit (legacy - usually empty since the tab is hidden).
            if hasattr(self, "file_path_edit") and self.file_path_edit is not None:
                path = self.file_path_edit.text().strip()
                if path and Path(path).exists():
                    return Path(path).read_text(encoding="utf-8", errors="replace")[:5000]
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)
        return ""

    # ----------------------------------------------------------------
    # File picker override - adds to the queue (req. #8)
    # ----------------------------------------------------------------
    def _pick_file(self) -> None:
        """V11.29: Override - picking a file (or files) enqueues them
        instead of overwriting ``file_path_edit``. The queue is the single
        source of truth for which files to translate.
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add file(s) to translate", "", "Text (*.txt *.md);;All files (*.*)"
        )
        if not paths:
            return
        for p in paths:
            if p not in self._file_queue:
                self._file_queue.append(p)
                self.file_queue_list.addItem(p)
        self._update_direction()
        self._refresh_default_output()

    def _add_translation_files(self) -> None:
        """V11.27/V11.29: Add one or more files to the queue."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add files to translate", "", "Text (*.txt *.md);;All files (*.*)"
        )
        if not paths:
            return
        for p in paths:
            if p not in self._file_queue:
                self._file_queue.append(p)
                self.file_queue_list.addItem(p)
        self._update_direction()
        self._refresh_default_output()

    def _remove_translation_file(self) -> None:
        """V11.27/V11.29: Remove the selected file from the queue."""
        row = self.file_queue_list.currentRow()
        if 0 <= row < len(self._file_queue):
            self._file_queue.pop(row)
            self.file_queue_list.takeItem(row)
        self._update_direction()
        self._refresh_default_output()

    def _clear_queue(self) -> None:
        """V11.29: Clear all files from the queue."""
        self._file_queue.clear()
        if hasattr(self, "file_queue_list"):
            self.file_queue_list.clear()
        self._update_direction()
        self._refresh_default_output()

    # ----------------------------------------------------------------
    # Default output filename / path (req. #9, #10)
    # ----------------------------------------------------------------
    @staticmethod
    def _sanitize_stem(stem: str) -> str:
        """Sanitize a filename stem: keep alphanumerics + -_., cap length."""
        safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in (stem or ""))
        safe = safe.strip("._-")
        return safe[:80] if safe else "output"

    def _default_output_filename(self, stem: str, lang: str, ext: str) -> str:
        """V11.29: Build the default output filename.

        - File mode: ``{stem}-{lang}-translation{ext}``
          (e.g. ``tiger-fa-translation.md``)
        - Paste mode: ``pasted-{lang}-translation{ext}``
          (e.g. ``pasted-fa-translation.md``)
        """
        safe_stem = self._sanitize_stem(stem)
        if not ext.startswith("."):
            ext = "." + ext
        return f"{safe_stem}-{lang}-translation{ext}"

    def _default_output_dir(self) -> str:
        """V11.29: Default output directory.

        Priority:
          1. The "save to" setting from the gear pop-up (if non-empty).
          2. The first queued file's directory.
          3. The user's home directory.
        """
        # 1. Gear-configured save-to folder.
        folder = getattr(self, "_save_to_folder", "") or ""
        if folder:
            try:
                Path(folder).mkdir(parents=True, exist_ok=True)
                return folder
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
        # 2. First queued file's directory.
        queue = getattr(self, "_file_queue", None) or []
        if queue:
            try:
                parent = Path(queue[0]).parent
                if parent.exists():
                    return str(parent)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
        # 3. User home.
        return str(Path.home())

    def _refresh_default_output(self) -> None:
        """V11.29: Re-fill the output path with the default name + dir,
        but only if the user hasn't manually edited the path (heuristic:
        the current path's stem ends with ``-translation``).
        """
        if not hasattr(self, "out_path_edit") or self.out_path_edit is None:
            return
        current = self.out_path_edit.text().strip()
        if current:
            # If the user typed a custom name (not -translation{ext}),
            # leave it alone.
            try:
                stem = Path(current).stem
            except Exception:
                stem = ""
            if not stem.endswith("-translation"):
                return
        src, tgt = self._detected_direction
        ext = self._resolved_format or ".md"
        # Read the format from the combo if _resolved_format isn't current.
        if hasattr(self, "fmt_combo") and self.fmt_combo is not None:
            combo_ext = self.fmt_combo.currentData()
            if combo_ext:
                ext = combo_ext
        out_dir = self._default_output_dir()
        if self._file_queue:
            stem = Path(self._file_queue[0]).stem
        else:
            stem = "pasted"
        filename = self._default_output_filename(stem, tgt, ext)
        self.out_path_edit.setText(str(Path(out_dir) / filename))

    # ----------------------------------------------------------------
    # gear Settings pop-up (req. #11)
    # ----------------------------------------------------------------
    def _open_settings(self) -> None:
        """V11.29: Open the gear settings pop-up.

        Contains:
          - Mode (literal / simplified)
          - Obsidian checkbox
          - Default save-to folder setting (persisted)

        On OK, writes the resolved values to ``self._resolved_mode``,
        ``self._resolved_obsidian`` (and ``self._save_to_folder``) and
        re-evaluates the default output path.
        """
        from PySide6.QtWidgets import (
            QCheckBox as _QChk,
        )
        from PySide6.QtWidgets import (
            QComboBox as _QCB,
        )
        from PySide6.QtWidgets import (
            QDialog as _QDlg,
        )
        from PySide6.QtWidgets import (
            QFileDialog as _QFD,
        )
        from PySide6.QtWidgets import (
            QHBoxLayout as _HL,
        )
        from PySide6.QtWidgets import (
            QLabel as _QL,
        )
        from PySide6.QtWidgets import (
            QLineEdit as _QLE,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        dlg = _QDlg(self)
        dlg.setWindowTitle("⚙ Translation Settings")
        dlg.setModal(True)
        dlg.setMinimumWidth(440)
        v = _VL(dlg)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)

        # -- Mode ---------------------------------------------------
        mode_lbl = _QL("Translation mode:")
        mode_lbl.setObjectName("Caption")
        v.addWidget(mode_lbl)
        mode_combo = _QCB()
        mode_combo.addItem("ترجمه تحت‌اللفظی (Literal — keep original tone)", "literal")
        mode_combo.addItem("ترجمه ساده (Simplified — everyday Farsi)", "simplified")
        mode_combo.setCurrentIndex(0 if self._resolved_mode == "literal" else 1)
        mode_combo.setToolTip(
            "Literal: translates word-for-word, keeping the original tone "
            "and wording.\n"
            "Simplified: translates + simplifies to everyday Farsi "
            "(simple, fluent) without being conversational."
        )
        v.addWidget(mode_combo)

        # -- Obsidian -----------------------------------------------
        obs_chk = _QChk("Obsidian-style markdown (callouts + front-matter)")
        obs_chk.setToolTip(
            "When ON and format is .md: wraps the translation in YAML "
            "front-matter and converts section headings into Obsidian "
            "callouts."
        )
        obs_chk.setChecked(bool(self._resolved_obsidian))
        v.addWidget(obs_chk)

        # -- Save-to folder -----------------------------------------
        folder_lbl = _QL("Default save-to folder (leave empty to use the source file's directory):")
        folder_lbl.setObjectName("Caption")
        v.addWidget(folder_lbl)
        folder_row = _HL()
        folder_edit = _QLE(self._save_to_folder or "")
        folder_edit.setPlaceholderText("(use source file's directory)")
        folder_btn = _QPB("Browse...")

        def _pick_folder() -> None:
            path = _QFD.getExistingDirectory(
                dlg,
                "Choose default save-to folder",
                folder_edit.text() or str(Path.home()),
            )
            if path:
                folder_edit.setText(path)

        folder_btn.clicked.connect(_pick_folder)
        folder_row.addWidget(folder_edit, 1)
        folder_row.addWidget(folder_btn)
        v.addLayout(folder_row)

        # -- OK / Cancel --------------------------------------------
        btn_row = _HL()
        btn_row.addStretch()
        cancel_btn = _QPB("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = _QPB("OK")
        ok_btn.setObjectName("Primary")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        v.addLayout(btn_row)

        if dlg.exec() == _QDlg.Accepted:
            self._resolved_mode = mode_combo.currentData() or "literal"
            self._resolved_obsidian = bool(obs_chk.isChecked())
            self._save_to_folder = folder_edit.text().strip()
            # Persist the save-to setting so it survives dialog reopens.
            self._save_setting("save_to_folder", self._save_to_folder)
            # Re-evaluate the default output path (dir may have changed).
            self._refresh_default_output()

    # ----------------------------------------------------------------
    # Model picker refresh (V11.24.2 - kept, called from showEvent)
    # ----------------------------------------------------------------
    def _refresh_models(self) -> None:
        """V11.29.3: Populate the model combo from /api/tags.
        No "Default" option — always shows the actual installed models.
        Prefers TranslateGemma-12B if installed, else the first model.
        """
        if not getattr(self, "model_combo", None):
            return
        from utils.network import list_ollama_models
        from utils.settings import Settings

        s = Settings()
        preferred = "translategemma-12b-it.Q4_K_M_mradermacher:latest"

        # Fetch installed models from Ollama.
        # V0.6.8 (audit B5): routed through utils.network.list_ollama_models
        # (safe_ollama_request → proxy-proof) — was a bare requests.get
        # that broke on machines with HTTP_PROXY set.
        ollama_url = (
            s.get("translation.endpoint", "http://localhost:11434/v1")
            or "http://localhost:11434/v1"
        )
        ollama_url = ollama_url.rstrip("/")
        if ollama_url.endswith("/v1"):
            ollama_url = ollama_url[:-3]
        ollama_url = ollama_url.rstrip("/")

        models: list[str] = []
        try:
            # V0.6.8 (review-loop follow-up): timeout=5 preserves the
            # original bare-call latency budget (the helper default is 10).
            models = [m for m in list_ollama_models(ollama_url, timeout=5) if m]
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)

        # Remember the current selection.
        current = self.model_combo.currentText().strip()
        self.model_combo.clear()

        if models:
            for m in models:
                self.model_combo.addItem(m, m)

            # V11.29.3: auto-select the preferred model if installed.
            # Otherwise keep the previous selection if it's still installed.
            # Otherwise select the first model.
            selected = False
            # Try preferred.
            for i in range(self.model_combo.count()):
                if preferred in self.model_combo.itemText(i):
                    self.model_combo.setCurrentIndex(i)
                    selected = True
                    break
            # Try previous selection.
            if not selected and current:
                for i in range(self.model_combo.count()):
                    if current in self.model_combo.itemText(i):
                        self.model_combo.setCurrentIndex(i)
                        selected = True
                        break
            # Fallback: first model.
            if not selected and self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
        else:
            # Ollama unreachable — seed with the preferred default.
            self.model_combo.addItem(preferred + "  (Ollama unreachable)", preferred)

        # V0.6.5: remember the installed list for the active-LLM fallback
        # resolution in _collect_options (a REAL installed model stays the
        # user's choice; anything else falls back to the active LLM).
        self._installed_models = models or []

    # ----------------------------------------------------------------
    # Options resolution (runs on the MAIN thread before _process)
    # ----------------------------------------------------------------
    def _collect_options(self) -> dict:
        """V11.29: Resolve all options on the MAIN thread before the
        background worker starts. Stored as instance attributes so
        ``_process`` (background thread) and ``_save_result`` (main
        thread) can read them without touching Qt widgets.
        """
        from core.translation.translation_engine import TranslationEngine
        from utils.settings import Settings

        Settings()  # V0.13: side-effect instantiation (warms the singleton)

        # -- Final direction auto-detection (uses current input) ----
        text = self._peek_input_text()
        if text and text.strip():
            try:
                self._detected_direction = TranslationEngine.auto_detect_direction(text)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
        src, tgt = self._detected_direction
        self._resolved_source_lang = src
        self._resolved_target_lang = tgt

        # -- Record start time for elapsed-time display -------------
        self._start_time = time.time()

        # -- Resolve model ------------------------------------------
        # V11.29.3: don't read from translation.model (may be stale from
        # a previous version). Use the combo's current data, or the combo's
        # current text, or the hardcoded 12B default.
        model_choice = self.model_combo.currentData() if self.model_combo else None
        if model_choice and model_choice != "__default__":
            self._resolved_model = model_choice
        elif self.model_combo and self.model_combo.currentText().strip():
            # The user typed a model name or selected one.
            typed = self.model_combo.currentText().strip()
            # Skip the "Default" display text.
            if "Default" not in typed and "not installed" not in typed:
                self._resolved_model = typed
            else:
                self._resolved_model = "translategemma-12b-it.Q4_K_M_mradermacher:latest"
        else:
            self._resolved_model = "translategemma-12b-it.Q4_K_M_mradermacher:latest"

        # -- V0.6.5: the active-LLM fallback ---------------------------
        # The user requirement: "the translation tool should fall back to
        # the CURRENT ACTIVE LLM (ollama or llama.cpp) when no dedicated
        # translation model is found." A dedicated model = a
        # translation-named entry in the combo (translategemma / translate
        # families). When none is present AND the combo's model isn't a
        # real installed translation model, route the whole run through
        # the active provider (summarisation.provider + its model — the
        # same resolution the Summarizer tool uses), via the engine's
        # provider-backed llm_complete transport.
        self._active_llm_fallback = False
        self._active_llm_info = ""
        combo_texts = (
            [self.model_combo.itemText(i).lower() for i in range(self.model_combo.count())]
            if self.model_combo
            else []
        )
        has_dedicated = any(
            ("translategemma" in t or "translate" in t) and "unreachable" not in t
            for t in combo_texts
        )
        if not has_dedicated:
            try:
                from core.llm.model_taxonomy import RIG_FALLBACK_MODEL

                _s = Settings()
                active_model = (
                    _s.get("quick_services.defaults.summarize_model", "")
                    or _s.get("summarisation.model", "")
                    or RIG_FALLBACK_MODEL
                )
                self._active_llm_fallback = True
                # Model resolution: keep ANY real installed model AND any
                # model the user TYPED (an editable combo — their pick is
                # authoritative); only the "unreachable" seeded default or
                # an empty selection swaps to the ACTIVE LLM's model (the
                # user requirement).
                installed = getattr(self, "_installed_models", []) or []
                current_text = (
                    (self.model_combo.currentText() or "").strip() if self.model_combo else ""
                )
                seeded_or_empty = not current_text or "unreachable" in current_text.lower()
                if self._resolved_model not in installed and seeded_or_empty:
                    self._resolved_model = active_model
                self._active_llm_info = (
                    f"{_s.get('summarisation.provider', 'ollama')} / {self._resolved_model}"
                )
            except Exception:
                logger.debug("active-llm fallback resolution failed", exc_info=True)

        # -- Resolve format (V11.29: removed "__default__" - always a real ext) --
        fmt = self.fmt_combo.currentData() if self.fmt_combo else ".md"
        self._resolved_format = fmt or ".md"

        # -- Mode + Obsidian come from the gear pop-up (already stored) --

        return {
            "source_lang": src,
            "target_lang": tgt,
            "mode": self._resolved_mode,
            "format": self._resolved_format,
            "model": self._resolved_model,
            "obsidian": self._resolved_obsidian,
        }

    def _get_output_suffix(self) -> str:
        if self.fmt_combo is not None:
            ext = self.fmt_combo.currentData()
            if ext:
                return ext
        return ".md"

    def _get_service_name(self) -> str:
        return "translation"

    # ----------------------------------------------------------------
    # Process - routes to multi-file queue or single-input flow
    # ----------------------------------------------------------------
    def _on_process(self) -> None:
        """V11.29.1: Route to multi-file queue mode if the queue is
        non-empty; otherwise fall back to the single-input flow.

        V11.29.1 fix: in multi-file mode, files are saved individually
        inside the worker thread. The summary string is shown in the
        status label + result preview, but _save_result is NOT called
        again (which was overwriting the real translation with the summary).
        """
        # Pre-fill the default output path if the user hasn't typed one.
        if not self.out_path_edit.text().strip():
            self._refresh_default_output()

        if not self._file_queue:
            # No files queued - use the normal single-input flow.
            super()._on_process()
            return

        # -- Multi-file queue mode ---------------------------------
        out_folder = self.out_path_edit.text().strip()
        if not out_folder:
            QMessageBox.warning(
                self,
                "No output",
                "Please choose where to save the translations (a folder for multi-file mode).",
            )
            return

        # If the output path looks like a file (has an extension), use
        # its parent directory as the output folder.
        from pathlib import Path as _P

        out_p = _P(out_folder)
        if out_p.is_file() or (not out_p.exists() and "." in out_p.name):
            out_folder = str(out_p.parent)
            out_p = _P(out_folder)

        # Collect options.
        options = self._collect_options()

        # Show processing UI.
        self.process_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Processing...")
        self._cancel_requested = False

        # Process each file in the queue on a background thread.
        def _run_queue():
            from pathlib import Path as _P2

            from core.outputs.service_formatters import write_output

            results: list[str] = []
            total = len(self._file_queue)
            for i, file_path in enumerate(self._file_queue):
                if self._cancel_requested:
                    break
                p = _P2(file_path)
                self._emit_progress(
                    int((i / total) * 100) if total > 0 else 0,
                    f"🌐 Translating file {i + 1}/{total}: {p.name}…",
                )
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    if not text.strip():
                        results.append(f"⚠️ {p.name} → empty file, skipped")
                        continue
                    # Translate using the engine.
                    translated = self._process(text, options)
                    # Save to {stem}-{lang}-translation{ext}.
                    ext = self._resolved_format or ".md"
                    out_file = _P2(out_folder) / (
                        f"{p.stem}-{self._resolved_target_lang}-translation{ext}"
                    )
                    ok, msg = write_output(
                        translated,
                        out_file,
                        fmt=ext,
                        title=f"Translation of {p.name}",
                        obsidian=self._resolved_obsidian,
                        source_filename=p.stem,
                        quality=self._resolved_mode,
                        model=self._resolved_model,
                    )
                    if ok:
                        results.append(f"✅ {p.name} → {out_file.name}")
                    else:
                        results.append(f"⚠️ {p.name} → {msg}")
                except Exception as e:
                    results.append(f"❌ {p.name} → {type(e).__name__}: {e}")

            elapsed = time.time() - (self._start_time or time.time())
            # V0.6.0 (T7): honest final progress — "✅" only when at least
            # one file actually translated.
            any_ok = any(r.strip().startswith("✅") for r in results)
            final_emoji = "✅" if any_ok else "⚠️"
            self._emit_progress(
                100,
                f"{final_emoji} All files processed — {self._format_elapsed(elapsed)}",
            )
            return "\n".join(results)

        self._worker = SimpleWorker(_run_queue)

        # V11.29.1: in multi-file mode, don't use the normal _on_finished
        # (which calls _save_result and would overwrite the real files with
        # the summary string). Instead, show the summary in the status +
        # result preview + success modal directly.
        #
        # V0.6.0 (T9): the slot is a BOUND METHOD of this QObject dialog.
        # It used to be a plain closure — plain-function slots have no
        # receiver thread affinity, so Qt executed it DIRECTLY ON THE
        # WORKER THREAD, where it touched widgets (result_preview's
        # QTextDocument, status_label) and called QTimer.singleShot from
        # the wrong thread — the exact "QTextDocument thread-safety
        # crash" class the V11.30 comments say this code avoids. Bound
        # methods of a QObject are auto-queued to the main thread.
        self._queue_out_folder = out_folder
        self._worker.finished.connect(self._on_queue_finished)
        self._worker.failed.connect(self._on_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_queue_finished(self, summary: str) -> None:
        """V11.29.1 + V0.6.0 (T9): show the multi-file queue summary on the
        MAIN thread (queued slot — see the wiring note in ``_on_process``).
        """
        self._reset_ui()
        self.result_preview.setPlainText(summary)
        self.result_preview.setVisible(True)
        self.status_label.setText(summary)
        self.again_btn.setVisible(True)
        # V11.30: defer the success modal via QTimer.singleShot(0, ...)
        # to prevent QTextDocument thread-safety crash.
        from PySide6.QtCore import QTimer

        # V0.6.0 (T7): never a success modal on failure — when every
        # queued file failed (no "✅" line in the summary), warn
        # instead of announcing "✅ Translation Complete".
        any_ok = any(line.strip().startswith("✅") for line in summary.splitlines())
        if any_ok:
            QTimer.singleShot(
                0,
                lambda: _show_success_modal(
                    self,
                    "✅ Translation Complete",
                    summary,
                    file_path=self._queue_out_folder,
                    on_try_another=self._on_try_another,
                ),
            )
        else:
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    self,
                    "⚠️ Translation Failed",
                    summary,
                ),
            )

    # ----------------------------------------------------------------
    # _process - delegates to TranslationEngine (V11.28, kept in V11.29)
    # ----------------------------------------------------------------
    def _process(self, input_text: str, options: dict) -> str:
        """V11.28/V11.29: Uses the robust TranslationEngine for all
        translation logic. Direction comes from ``options`` (auto-detected
        by ``_collect_options`` on the main thread).

        The engine handles:
          - Retry logic (3 attempts per line with fallback prompts).
          - Refusal detection + retry.
          - Repetition-loop detection.
          - Markdown preservation (bullets, headings, blockquotes).
          - Dynamic consistency memory (learned term translations).
          - Language-pair prompt for TranslateGemma (no echo, no refusals).
          - Full instruction prompt for non-TranslateGemma (with mode).
          - Elapsed-time tracking.
        """
        target_lang = options.get("target_lang", "fa")
        source_lang = options.get("source_lang", "en")
        mode = self._resolved_mode

        from utils.settings import Settings

        s = Settings()
        ollama_url = (
            s.get("translation.endpoint", "http://localhost:11434/v1")
            or "http://localhost:11434/v1"
        )
        model = self._resolved_model

        try:
            from core.translation.translation_engine import ModelNotFoundError, TranslationEngine

            # V0.6.5: the active-LLM fallback transport. When no dedicated
            # translation model was found (see _collect_options), every
            # line call rides the ACTIVE provider (ollama / llama.cpp /
            # OpenAI-compat) through create_provider — the engine's raw
            # /api/generate transport stays for the dedicated-model path.
            llm_complete = None
            if getattr(self, "_active_llm_fallback", False):
                from core.llm.llm_provider import create_provider

                provider_name = s.get("summarisation.provider", "ollama")
                try:
                    provider = create_provider(
                        provider=provider_name,
                        settings=s,
                        log_callback=lambda msg, level="INFO": None,
                    )
                    fallback_model = self._resolved_model

                    def _llm_complete(prompt: str) -> str | None:
                        return provider.complete_streaming(
                            prompt=prompt,
                            temperature=0.3,
                            max_tokens=2048,
                            model=fallback_model,
                        )

                    llm_complete = _llm_complete
                    self._emit_progress(
                        0,
                        f"ℹ️ No dedicated translation model — using the active LLM "
                        f"({self._active_llm_info}).",
                    )
                except Exception as e:
                    logger.warning("active-LLM fallback provider failed: %s", e)
                    # Provider unreachable → engine tries the raw path and
                    # surfaces its honest error.

            engine = TranslationEngine(
                ollama_url=ollama_url,
                model=model,
                source_lang=source_lang,
                target_lang=target_lang,
                mode=mode,
                temperature=0.3,
                progress_callback=self._emit_progress,
                log_callback=lambda msg, level="INFO": None,
                llm_complete=llm_complete,
            )
            return engine.translate_text(input_text)
        except ModelNotFoundError as e:
            # V11.29.3: model not installed — return clear error, don't
            # silently copy-paste the original text.
            # V0.6.0 (T2): shared.py ``_on_finished`` (V11.31.12 contract)
            # routes ONLY strings starting with "Error:" to the failure
            # branch — the old "❌ {e}" / "Translation error: ..." shapes
            # were written to the output file and reported as ✅ success.
            return f"Error: {e}"
        except Exception as e:
            return f"Error: translation failed — {type(e).__name__}: {e}"

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        """Format elapsed seconds as 'Xm Ys' or 'Ys'."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"

    # ----------------------------------------------------------------
    # _save_result - uses write_output (V11.27, kept in V11.29)
    # ----------------------------------------------------------------
    def _save_result(self, result: Any, path: Path) -> str | None:
        """V11.27/V11.29: Override to use the shared ``write_output``
        formatter. Returns the ACTUAL saved path (with adjusted
        extension) so ``_on_finished`` can show the correct filename.

        ``_resolved_format``, ``_resolved_obsidian``, ``_resolved_mode``,
        ``_resolved_model``, and ``_resolved_target_lang`` were all set on
        the main thread in ``_collect_options``, so they're safe to read
        here.
        """
        if not isinstance(result, str):
            return None
        from core.outputs.service_formatters import write_output

        ext = self._resolved_format or ".md"
        # Adjust the path extension to match the resolved format.
        if path.suffix.lower() != ext.lower():
            path = path.with_suffix(ext)
        lang = self._resolved_target_lang or "fa"
        ok, msg = write_output(
            result,
            path,
            fmt=ext,
            title=f"Translation ({lang})",
            obsidian=self._resolved_obsidian,
            source_filename="translation",  # clean filename, not path.stem
            quality=self._resolved_mode,  # "literal" or "simplified"
            model=self._resolved_model,  # actual model name
        )
        if not ok:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result, encoding="utf-8")
        return str(path)

    # ----------------------------------------------------------------
    # _on_try_another - reset for the next file
    # ----------------------------------------------------------------
    def _on_try_another(self) -> None:
        """V11.29: Reset the dialog for the next translation. Calls the
        base implementation (which clears text, file_path_edit, output
        path, queue, result preview, and the again button), then
        re-detects direction (no input -> default en->fa) and re-fills
        the default output path.
        """
        super()._on_try_another()
        # Reset direction to the default (no input yet).
        self._detected_direction = ("en", "fa")
        if hasattr(self, "direction_lbl") and self.direction_lbl is not None:
            self.direction_lbl.setText("EN → FA  (auto-detected)")
        # Pre-fill the default output path for paste mode.
        self._refresh_default_output()
        # Allow live model refresh on next show (in case the user adds a
        # new model in Ollama between translations).
        self._models_refreshed_on_show = False
