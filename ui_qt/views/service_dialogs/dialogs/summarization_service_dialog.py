"""Summarization Service dialog (V18.20.4.6, P5 / O-b2 split).

SummarizationServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

from PySide6.QtCore import Qt

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QWidget,
)

from controller import Controller

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model (core.llm.model_taxonomy is a leaf module — stdlib-only, no cycle).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    PlainTextTextEdit,
    _confirm_close_with_running_worker,
    _show_success_modal,
)


class SummarizationServiceDialog(QDialog):
    """V11: Standalone Summarization — paste text → get summary + keypoints.

    V13.25.0 (P1.2): Now delegates to core modules instead of duplicating logic:
    - ``PromptManager.render()`` for prompt building (user's custom prompts work)
    - ``llm_provider.create_provider().complete_streaming()`` for LLM calls
      (gets OllamaSupervisor, retry, proxy-proof HTTP, response cache)
    - ``response_parser.parse_response()`` for parsing XML-tagged output
    - ``utils.network.list_ollama_models()`` for model listing (proxy-proof)
    - ``summarisation.endpoint`` for the Ollama URL (was wrong key: ocr.ollama_url)

    UI: text area, model picker, quality dropdown, output path, single Convert
    button, synchronous execution with streaming for UI responsiveness.

    V11.17: Added model picker (auto-populated from /api/tags), pre-flight
    model check, and actionable 404/error messages that list available
    models + the exact `ollama pull` command to fix the problem.

    V11.18:
      - **Multi-file input**: a "Pick Files" tab now accepts multiple
        .txt/.md files; each is summarized independently and saved as
        ``{stem}_{quality}_summary{ext}``.
      - **Output format dropdown**: ``.md``, ``.docx``, ``.pdf`` (via the
        shared ``service_formatters`` module). python-docx is in
        requirements.txt; the PDF path needs WeasyPrint or ReportLab —
        neither is in requirements.txt (V0.6.0 docstring correction: the
        old text claimed "reportlab is in requirements.txt", which was
        never true), so on a bare install ``write_pdf`` degrades to
        writing the ``.md`` next to the requested ``.pdf``.
      - **Obsidian-style markdown** toggle: when on (and format is .md),
        the summary is wrapped in YAML front-matter + Obsidian callouts
        (``> [!summary]``, ``> [!info]``, …) so it drops cleanly into an
        Obsidian vault.
      - **Auto output filename**: ``{stem}_{quality}_summary{ext}``
        (e.g. ``report_fast_summary.md``). For multi-file, the output
        folder is used and each file gets its own auto-named output.
      - **Try Another File** button after a run: clears inputs/outputs so
        the user can summarize the next file without reopening the dialog.
    """

    # Default model used when settings has nothing and Ollama is unreachable.
    # V18.20.4.12 (W-a10): was the NON-empero variant
    # "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest" — a KNOWN-BAD tag that
    # 404s on the rig (utils/settings.py:989-990 documents the mismatch vs
    # the actual installed ...-empero-v3 tag). RIG_FALLBACK_MODEL is the
    # working rig tag; the combo is overwritten with the live /api/tags
    # list as soon as Ollama answers.
    _DEFAULT_MODEL = RIG_FALLBACK_MODEL

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Σ Summarization Service")
        self.setMinimumSize(640, 540)
        self.setModal(True)

        from PySide6.QtWidgets import (
            QCheckBox as _QChB,
        )
        from PySide6.QtWidgets import (
            QComboBox as _QCB,
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
            QListWidget as _QLW,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QTabWidget as _QTW,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        # V11.66.0: PlainTextTextEdit is defined at the top of this file,
        # NOT in PySide6.QtWidgets. This was causing an ImportError.
        _QTE = PlainTextTextEdit

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("Σ Summarization Service")
        title.setObjectName("H2")
        lay.addWidget(title)

        # ── Input tabs: paste text / pick files (multi) ───────────────
        self.tabs = _QTW()
        # Tab 1: paste text
        text_tab = QWidget()
        text_lay = _VL(text_tab)
        self.text_input = _QTE()
        self.text_input.setPlaceholderText("Paste your text here…")
        self.text_input.setAcceptRichText(False)  # V11.31: strip styling on paste
        text_lay.addWidget(self.text_input)
        self.tabs.addTab(text_tab, "📋 Paste Text")
        # Tab 2: pick files (multi) — V11.18
        file_tab = QWidget()
        file_lay = _VL(file_tab)
        self.file_list = _QLW()
        self.file_list.setMinimumHeight(100)
        self.file_list.setMaximumHeight(160)
        file_btn_row = _HL()
        add_btn = _QPB("Add Files…")
        add_btn.clicked.connect(self._add_files)
        rm_btn = _QPB("Remove")
        rm_btn.clicked.connect(self._remove_file)
        file_btn_row.addWidget(add_btn)
        file_btn_row.addWidget(rm_btn)
        file_btn_row.addStretch()
        hint_lbl = _QL("Add multiple .txt / .md files — each is summarized independently.")
        hint_lbl.setObjectName("Caption")
        file_btn_row.addWidget(hint_lbl)
        file_lay.addWidget(self.file_list)
        file_lay.addLayout(file_btn_row)
        self.tabs.addTab(file_tab, "📁 Pick Files (multi)")
        lay.addWidget(self.tabs)

        # ── Model picker row ───────────────────────────────────────────
        model_row = _HL()
        model_row.setSpacing(8)
        model_row.addWidget(_QL("Model:"))
        self.model_combo = _QCB()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(320)
        model_row.addWidget(self.model_combo, 1)
        self.refresh_btn = _QPB("🔄 Refresh")
        self.refresh_btn.setToolTip("Re-fetch the list of installed Ollama models")
        self.refresh_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self.refresh_btn)
        lay.addLayout(model_row)

        # ── Options row: quality + output format ──────────────────────
        # V11.19: each combo has a "Default" option (data="__default__") that
        # reads from quick_services.defaults.* at run-time.
        opt_row = _HL()
        opt_row.setSpacing(8)
        opt_row.addWidget(_QL("Quality:"))
        self.quality_combo = _QCB()
        self.quality_combo.addItem("Default (change in Settings)", "__default__")
        self.quality_combo.addItem("Fast (exec summary + 5 keypoints)", "fast")
        self.quality_combo.addItem("Standard (exec + 10 keypoints + thorough)", "standard")
        self.quality_combo.addItem("Thorough (detailed + analysis)", "thorough")
        opt_row.addWidget(self.quality_combo)
        opt_row.addSpacing(16)
        opt_row.addWidget(_QL("Format:"))
        self.fmt_combo = _QCB()
        self.fmt_combo.addItem("Default (change in Settings)", "__default__")
        self.fmt_combo.addItem("Markdown (.md)", ".md")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        opt_row.addWidget(self.fmt_combo)
        opt_row.addStretch()
        lay.addLayout(opt_row)

        # ── Obsidian toggle (V11.18) ──────────────────────────────────
        obs_row = _HL()
        self.obsidian_chk = _QChB(
            "Obsidian-style markdown (callouts + front-matter — for paste-into-Obsidian)"
        )
        self.obsidian_chk.setToolTip(
            "When ON and format is .md: wraps the summary in YAML front-matter and "
            "converts section headings into Obsidian callouts (> [!summary], > [!info], …)."
        )
        # V11.19: tri-state — Unchecked=Force off, PartiallyChecked=Default (use setting), Checked=Force on.
        self.obsidian_chk.setTristate(True)
        # Start in "Default" state (follows quick_services.defaults.summarize_obsidian).
        self.obsidian_chk.setCheckState(Qt.PartiallyChecked)
        self.obsidian_chk.setEnabled(True)
        obs_row.addWidget(self.obsidian_chk)
        obs_row.addStretch()
        lay.addLayout(obs_row)

        # ── Output row ────────────────────────────────────────────────
        out_row = _HL()
        out_row.setSpacing(8)
        out_row.addWidget(_QL("Save to:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText(
            "Single file: full path  |  Multi-file: output FOLDER (files auto-named {stem}_{quality}_summary{ext})"
        )
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        lay.addLayout(out_row)

        # ── Status ────────────────────────────────────────────────────
        # V11.20: bigger, bolder status label + a busy progress bar during
        # processing so the user gets clear visual feedback.
        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(50)
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status_label, 1)

        # V11.20: busy progress bar — visible only during processing.
        from PySide6.QtWidgets import QProgressBar as _QPB2

        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 0)  # busy/indeterminate mode
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = _HL()
        btn_row.addStretch()
        self.again_btn = _QPB("🔄 Try Another File")
        self.again_btn.setObjectName("Compact")
        self.again_btn.setVisible(False)
        self.again_btn.clicked.connect(self._on_try_another)
        self.action_btn = _QPB("Summarize")
        self.action_btn.setObjectName("Primary")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.again_btn)
        btn_row.addWidget(self.action_btn)
        lay.addLayout(btn_row)

        # Populate the model picker on first show.
        self._last_known_models: list[str] = []
        self._files: list[str] = []  # V11.18: multi-file list
        # V18.20.4.5 (W-b5/T-b2): the background summarization worker
        # (SimpleWorker).
        self._worker: SimpleWorker | None = None
        self._refresh_models()

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the summarization
        # worker runs — the "QThread: Destroyed while thread is still
        # running" abort class. Ask; on "close anyway" detach the worker
        # so the LLM loop's result is discarded, not crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    # ── Ollama helpers ────────────────────────────────────────────────

    # V13.25.0 (P1.2): All Ollama/LLM logic now delegates to core modules.
    # Previously this dialog had its own _ollama_base_url, _fetch_installed_models,
    # _build_prompt, and _call_ollama — duplicating llm_provider, PromptManager,
    # response_parser, and utils.network. User's custom prompts were ignored;
    # no supervisor/retry/cache; wrong settings key (ocr.ollama_url).

    @staticmethod
    def _ollama_base_url() -> str:
        """V13.25.0: Read the canonical Ollama URL from summarisation.endpoint.

        Previously read ``ocr.ollama_url`` (wrong namespace — that's for OCR).
        Now reads ``summarisation.endpoint`` (same key the Summarizer uses).
        """
        from utils.settings import Settings

        s = Settings()
        url = s.get("summarisation.endpoint", "http://localhost:11434")
        if not url:
            url = "http://localhost:11434"
        # Strip /v1 suffix if present — /api/tags needs the base URL
        if url.endswith("/v1"):
            url = url[:-3]
        return url.rstrip("/")

    def _fetch_installed_models(self, timeout: float = 5.0) -> list[str] | None:
        """V13.25.0: Delegate to utils.network.list_ollama_models (proxy-proof).

        Previously called ``requests.get(.../api/tags)`` directly — broke on
        machines with HTTP_PROXY set. Now uses ``safe_ollama_request`` via
        ``utils.network.list_ollama_models``.

        Returns the list of model names, or None if unreachable (empty list
        from list_ollama_models means Ollama is up but has no models).
        """
        from utils.network import list_ollama_models

        base = self._ollama_base_url()
        # list_ollama_models returns [] on connection failure (not None),
        # so we need to distinguish "unreachable" from "empty".
        # We do a quick reachability check first.
        import requests as _req

        try:
            _req.get(f"{base}/api/tags", timeout=timeout)
        except Exception:
            return None  # unreachable
        models = list_ollama_models(base)
        return models

    def _refresh_models(self) -> None:
        """Populate the model combo from /api/tags, keeping the current choice.

        V11.19: The first item is always "Default Model (change in Settings)"
        with data ``"__default__"`` — when selected, the dialog resolves the
        actual model at run-time from ``quick_services.defaults.summarize_model``
        (falling back to ``summarisation.model``).
        """
        from utils.settings import Settings

        s = Settings()
        configured = s.get("summarisation.model", self._DEFAULT_MODEL)

        models = self._fetch_installed_models()
        self._last_known_models = models or []

        # Remember the current selection (by data, not text — "Default" is special).
        current_data = self.model_combo.currentData()
        current_text = self.model_combo.currentText().strip()
        self.model_combo.clear()

        # V11.19: "Default Model" sentinel — always first.
        self.model_combo.addItem("Default Model (change in Settings)", "__default__")

        if models:
            for m in models:
                self.model_combo.addItem(m, m)
            if configured not in models:
                # Show the configured-but-missing model so the user sees it.
                self.model_combo.addItem(configured, configured)
                idx_missing = self.model_combo.count() - 1
                self.model_combo.setItemData(
                    idx_missing, "⚠️ not installed — pull it first", role=Qt.ToolTipRole
                )
        else:
            self.model_combo.addItem(configured, configured)
            self.model_combo.setItemData(
                self.model_combo.count() - 1,
                "Ollama unreachable — showing configured default. Start Ollama and click Refresh.",
                role=Qt.ToolTipRole,
            )

        # Restore selection.
        # Priority: previous data "__default__" → previous text match → configured.
        if current_data == "__default__":
            self.model_combo.setCurrentIndex(0)
        elif current_text and current_text != "Default Model (change in Settings)":
            idx = self.model_combo.findText(current_text)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(current_text)
        else:
            # First open: default to "Default Model" (index 0).
            self.model_combo.setCurrentIndex(0)

        if models is None:
            self.status_label.setText(
                "⚠️ Could not reach Ollama to list models. Start it with `ollama serve` then click 🔄 Refresh."
            )
        elif not models:
            self.status_label.setText(
                "⚠️ Ollama is running but has no models installed. "
                "Pull one with e.g. `ollama pull llama3.1:8b` then click 🔄 Refresh."
            )
        else:
            if configured not in models:
                self.status_label.setText(
                    f"⚠️ Configured model '{configured}' is not installed. "
                    f"{len(models)} model(s) available — pick one above or pull it."
                )
            else:
                self.status_label.setText(f"✅ Ollama online — {len(models)} model(s) available.")

    # ── File / action helpers ─────────────────────────────────────────

    def _add_files(self):
        """V11.18: Add multiple text/markdown files to the batch list."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add text files", "", "Text (*.txt *.md);;All files (*.*)"
        )
        if paths:
            for p in paths:
                if p not in self._files:
                    self._files.append(p)
                    self.file_list.addItem(p)

    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0 and row < len(self._files):
            self._files.pop(row)
            self.file_list.takeItem(row)

    def _pick_output(self):
        # If on the multi-file tab, pick a FOLDER; otherwise pick a FILE.
        if self.tabs.currentIndex() == 1:
            folder = QFileDialog.getExistingDirectory(
                self, "Choose output folder for summaries", ""
            )
            if folder:
                self.out_edit.setText(folder)
        else:
            # V11.67.0: resolve "__default__" to a real extension before using it.
            # Previously, ext was "__default__" which caused:
            # 1. The file dialog to show "All files" instead of "Markdown"
            # 2. The extension "__default__" to be appended to the filename
            #    (e.g., "summary.md__default__" — unreadable file!)
            ext = self.fmt_combo.currentData()
            if not ext or ext == "__default__":
                from utils.settings import Settings

                ext = Settings().get("quick_services.defaults.summarize_format", ".md") or ".md"
            filter_str = {
                ".md": "Markdown (*.md)",
                ".docx": "Word document (*.docx)",
                ".pdf": "PDF (*.pdf)",
            }.get(ext, "All files (*.*)")
            path, _ = QFileDialog.getSaveFileName(
                self, "Save summary as", "", f"{filter_str};;All files (*.*)"
            )
            if path:
                # V11.67.0: only append the extension if the path doesn't
                # already end with a valid extension. Don't append if the
                # user already typed .md/.docx/.pdf manually.
                from pathlib import Path as _P

                p = _P(path)
                if not p.suffix or p.suffix.lower() not in (".md", ".docx", ".pdf", ".txt"):
                    if not path.endswith(ext):
                        path += ext
                self.out_edit.setText(path)

    def _on_format_changed(self):
        """V11.18/V11.19: When the format dropdown changes, toggle the Obsidian
        checkbox enabled-state. Only meaningful for .md. The "__default__"
        sentinel resolves to the setting's default format — if that's .md,
        Obsidian stays enabled.
        """
        ext = self.fmt_combo.currentData() or ".md"
        if ext == "__default__":
            # Resolve from settings to decide whether Obsidian applies.
            from utils.settings import Settings

            ext = Settings().get("quick_services.defaults.summarize_format", ".md") or ".md"
        self.obsidian_chk.setEnabled(ext == ".md")
        if ext != ".md":
            # Keep the tri-state but force to off when format isn't .md.
            self.obsidian_chk.setCheckState(Qt.Unchecked)

    def _on_action(self):
        if self.action_btn.text() == "Close":
            self.accept()
            return
        self._do_summarize()

    def _on_try_another(self):
        """V11.18: Clear inputs/outputs for the next batch."""
        self.text_input.clear()
        self._files.clear()
        self.file_list.clear()
        self.out_edit.clear()
        # V11.19: reset model/quality/format to "Default", obsidian to PartiallyChecked.
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)  # "Default Model"
        if self.quality_combo.count() > 0:
            self.quality_combo.setCurrentIndex(0)  # "Default"
        if self.fmt_combo.count() > 0:
            self.fmt_combo.setCurrentIndex(0)  # "Default"
        self.obsidian_chk.setCheckState(Qt.PartiallyChecked)
        self.status_label.setText(
            "Ready for the next file — paste text or add files and click Summarize."
        )
        self.again_btn.setVisible(False)
        self.action_btn.setText("Summarize")
        self.action_btn.setEnabled(True)
        self.tabs.setCurrentIndex(0)

    def _get_input_text(self) -> str:
        if self.tabs.currentIndex() == 0:
            return self.text_input.toPlainText()
        else:
            # Multi-file tab — return empty; _do_summarize handles the list.
            return ""

    # ── Prompt builder ────────────────────────────────────────────────

    # V13.25.0 (P1.2): Prompt building now delegates to PromptManager.
    # Previously had 3 hardcoded prompt templates (fast/standard/thorough)
    # that bypassed the user's custom prompts in ~/.elixir/prompts/.
    # Now uses the same prompt bank the Summarizer uses — user's custom
    # prompts work, anti-hallucination language is built in, content-type
    # presets are respected.

    @staticmethod
    def _build_prompt(input_text: str, quality: str) -> tuple[str, int]:
        """Build the summarization prompt using the PromptManager.

        V13.25.0: Delegates to ``PromptManager.render("default", ...)`` —
        the same prompt bank the Summarizer uses. User's custom prompts in
        ``~/.elixir/prompts/default.md`` are respected.

        The prompt bank template produces XML-tagged output
        (``<executive_summary>``, ``<bullet_points>``, ``<thorough_summary>``)
        which is parsed by ``response_parser.parse_response()`` after the
        LLM call.

        Quality controls max_tokens (how much the LLM writes):
        - fast: 1024 tokens (~500 words)
        - standard: 2048 tokens (~1000 words)
        - thorough: 4096 tokens (~2000 words)

        Returns ``(prompt, max_tokens)``.
        """
        from core.summarisation.prompt_manager import PromptManager

        pm = PromptManager()
        heading = "Pasted Text"
        lang = ""  # let the prompt template decide

        # Try the user's custom default prompt, fall back to built-in
        rendered = pm.render("default", heading, input_text, lang)
        if not rendered:
            # Fallback: minimal prompt (shouldn't happen — PromptManager
            # copies built-ins to ~/.elixir/prompts/ on first run)
            rendered = (
                "You are an expert summariser.\n\n"
                f'Summarising: "{heading}"\n\n'
                f"Chapter content:\n{input_text}\n\n"
                "Output ONLY the three XML sections:\n"
                "<executive_summary>...</executive_summary>\n"
                "<bullet_points>...</bullet_points>\n"
                "<thorough_summary>...</thorough_summary>"
            )

        # Map quality → max_tokens
        max_tokens = {"fast": 1024, "standard": 2048, "thorough": 4096}.get(quality, 2048)
        return rendered, max_tokens

    def _call_llm(
        self, model: str, prompt: str, max_tokens: int, temp: float, report=None
    ) -> tuple[str | None, str | None]:
        """V13.25.0: Call the LLM via llm_provider (not direct requests.post).

        Delegates to ``llm_provider.create_provider()`` +
        ``complete_streaming()`` — gets:
        - OllamaSupervisor crash recovery (auto-restart after 3 failures)
        - Retry with backoff
        - Proxy-proof HTTP (safe_ollama_request pattern)
        - Response cache (if enabled)
        - <think> block stripping (in response_parser)

        Streaming progress: V18.20.4.5 (W-b5) — when ``report`` is
        provided (a callable ``(pct, msg)`` — the worker's queued progress
        emit), every 20th chunk is reported via ``report(0, html)`` so the
        update lands on the MAIN thread. When ``report`` is None (legacy
        main-thread callers), the status label is updated directly. The
        old ``QApplication.processEvents()`` repaint hack is gone from
        both paths — it caused the same re-entrancy class V11.29.2
        removed from ``BaseServiceDialog._on_progress``.

        Returns ``(text, error_msg)``. On success, error_msg is None.
        """
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings

        s = Settings()
        provider_name = s.get("summarisation.provider", "ollama")

        # Create the provider (OllamaProvider / OpenAICompatProvider / ClaudeProvider)
        try:
            provider = create_provider(
                provider=provider_name,
                settings=s,
                log_callback=lambda msg, level="INFO": None,  # silent — dialog has its own status
            )
        except Exception as e:
            return None, f"❌ Cannot create LLM provider: {type(e).__name__}: {e}"

        # Streaming callback — report progress.
        # V18.20.4.5 (W-b5): with ``report`` (worker thread), chunks ride
        # the queued progress signal — emitting from the worker thread
        # queues the slot onto the main thread (BaseWorker contract).
        # The legacy no-report path updates the status label directly
        # (main-thread callers only).
        chunk_count = [0]  # mutable closure

        def _on_chunk(accumulated_text: str):
            chunk_count[0] += 1
            if chunk_count[0] % 20 == 0:
                html = (
                    f"<div style='font-size:15px; font-weight:600;'>"
                    f"🤖 Generating… <span style='color: var(--primary);'>{len(accumulated_text):,} chars</span>"
                    f"</div>"
                )
                if report is not None:
                    report(0, html)
                else:
                    self.status_label.setText(html)

        try:
            result = provider.complete_streaming(
                prompt=prompt,
                temperature=temp,
                max_tokens=max_tokens,
                model=model,
                on_chunk=_on_chunk,
            )
        except Exception as e:
            return None, f"❌ LLM call failed: {type(e).__name__}: {e}"

        if not result or not result.strip():
            # V0.6.0 (S3): the old hint was Ollama-specific ("check `ollama
            # logs` for OOM errors") — for the llama.cpp / OpenAI-compat /
            # Claude providers that advice points at the wrong backend (a
            # refused llama-server connection lands here as an empty
            # result, since complete_streaming returns None on transport
            # failure). Name the actual provider.
            return None, (
                f"❌ LLM returned an empty response for model '<b>{model}</b>'.<br>"
                f"This usually means the model failed to load or the "
                f"<b>{provider_name}</b> backend is unreachable — check the "
                f"backend is running and the model name is correct, or try a "
                f"smaller model."
            )

        # Strip <think> blocks (response_parser also does this, but do it
        # here too so the streaming status display is clean)
        from core.summarisation.response_parser import strip_thinking

        result = strip_thinking(result)
        return result, None

    # ── Main summarize path ───────────────────────────────────────────

    def _do_summarize(self):
        from pathlib import Path as _P

        from utils.settings import Settings

        # V18.20.4.5 (W-b5): re-entrancy guard — a second click while a
        # batch summarizes would spawn a second LLM worker.
        if self._worker is not None and self._worker.is_running():
            self.status_label.setText(
                "⏳ Already summarizing — wait for the current batch to finish."
            )
            return

        # V11.19: resolve "__default__" sentinels from quick_services.defaults.*
        s = Settings()

        # ── Model ──────────────────────────────────────────────────────
        model_data = self.model_combo.currentData()
        if model_data == "__default__" or not model_data:
            # Use the default from settings, falling back to summarisation.model.
            model = s.get("quick_services.defaults.summarize_model", "") or s.get(
                "summarisation.model", self._DEFAULT_MODEL
            )
        else:
            model = model_data
        if not model:
            self.status_label.setText(
                "⚠️ Please pick or type an Ollama model name (or set a default in Settings)."
            )
            return

        # ── Quality ────────────────────────────────────────────────────
        quality = self.quality_combo.currentData()
        if quality == "__default__" or not quality:
            quality = s.get("quick_services.defaults.summarize_quality", "standard") or "standard"

        # ── Format ─────────────────────────────────────────────────────
        ext = self.fmt_combo.currentData()
        if ext == "__default__" or not ext:
            ext = s.get("quick_services.defaults.summarize_format", ".md") or ".md"

        # ── Obsidian (tri-state: Unchecked=use default, PartiallyChecked=off, Checked=on) ──
        obs_state = self.obsidian_chk.checkState()
        if obs_state == Qt.PartiallyChecked:
            # "Default" — follow the setting
            obsidian = (
                bool(s.get("quick_services.defaults.summarize_obsidian", False)) and ext == ".md"
            )
        elif obs_state == Qt.Checked:
            obsidian = ext == ".md"
        else:  # Qt.Unchecked → user explicitly turned it off
            obsidian = False

        # Determine input mode + validate
        is_multi = self.tabs.currentIndex() == 1
        if is_multi:
            if not self._files:
                self.status_label.setText(
                    "⚠️ Add at least one file to the list (or switch to the Paste Text tab)."
                )
                return
            out_folder = self.out_edit.text().strip()
            if not out_folder:
                self.status_label.setText("⚠️ Please choose an output folder for the summaries.")
                return
            inputs: list[tuple[str, str]] = []  # (stem, text)
            for fp in self._files:
                try:
                    txt = _P(fp).read_text(encoding="utf-8", errors="replace")
                    if txt.strip():
                        inputs.append((_P(fp).stem, txt))
                except Exception as e:
                    self.status_label.setText(f"❌ Cannot read {_P(fp).name}: {e}")
                    return
            if not inputs:
                self.status_label.setText("⚠️ None of the selected files contained readable text.")
                return
        else:
            input_text = self.text_input.toPlainText()
            if not input_text.strip():
                self.status_label.setText("⚠️ Please paste text (or switch to the Pick Files tab).")
                return
            if len(input_text.strip()) < 100:
                self.status_label.setText(
                    "⚠️ Text too short (need at least 100 characters for a meaningful summary)."
                )
                return
            out_path = self.out_edit.text().strip()
            if not out_path:
                self.status_label.setText("⚠️ Please choose where to save the summary.")
                return
            inputs = [("pasted", input_text)]
            # For single paste mode, the out_path is a full file path (not a folder).
            # We'll override the auto-naming below.

        s = Settings()
        temp = float(s.get("summarisation.temperature", 0.6))

        # V18.20.4.5 (W-b5): the model pre-flight check + the per-input LLM
        # loop moved OFF the UI thread. OLD defect: the 3s /api/tags probe
        # and every streaming LLM call (min per input) ran inline with
        # status_label + QApplication.processEvents() hacks — the UI froze
        # between chunks and was re-entrant. Now: validation stays here (it
        # only reads widgets); _summarize_work does the pure LLM/file work
        # and reports through the worker's queued progress signal; the
        # completion UI (incl. the settings persistence and the model-combo
        # refresh) lands in _on_summarize_finished on the MAIN thread.

        # Normalize the branch-local output targets into plain values the
        # worker can capture (only one is meaningful per mode).
        if is_multi:
            out_path = None
        else:
            out_folder = None

        # Show processing — V11.20: bigger text + busy progress bar.
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Processing…")
        self.progress_bar.setVisible(True)

        # The lambda referencing self._worker is safe: Python closures
        # late-bind, so at call time (worker thread) the attribute exists
        # and refers to THIS worker.
        self._worker = SimpleWorker(
            lambda: self._summarize_work(
                inputs,
                is_multi,
                out_folder,
                out_path,
                model,
                model_data,
                quality,
                ext,
                obsidian,
                temp,
                report=self._worker.progress.emit,
            )
        )
        self._worker.progress.connect(self._on_summarize_progress)
        self._worker.finished.connect(self._on_summarize_finished)
        self._worker.failed.connect(self._on_summarize_failed)
        self._worker.start()

    def _summarize_work(
        self,
        inputs,
        is_multi,
        out_folder,
        out_path,
        model,
        model_data,
        quality,
        ext,
        obsidian,
        temp,
        report=None,
    ) -> dict:
        """V18.20.4.5 (W-b5): the pre-flight check + per-input LLM loop,
        worker-thread edition.

        Pure LLM/file work — NO widget access. Per-input progress and
        streaming chunks go through ``report(pct, msg)`` (the worker's
        queued progress signal → main thread). A missing model returns an
        error-result dict; the model combo refresh happens in the FINISHED
        handler on the main thread, never here. Returns the plain result
        dict consumed by ``_on_summarize_finished``.
        """
        from pathlib import Path as _P

        from core.outputs.service_formatters import write_output
        from core.summarisation.response_parser import parse_response

        # ── Pre-flight: verify the model exists. V11.20: short timeout (3s)
        # so a slow Ollama doesn't hang; if the check itself times out, skip
        # it — the generate call will catch a real 404 anyway.
        # V18.20.4.5 (W-b5): this used to run ON the UI thread (a silent
        # 3s freeze); it now reports "Verifying model…" and runs here.
        if report is not None:
            report(0, "Verifying model…")
        # V0.6.0 (S1 fix): the pre-flight speaks the OLLAMA /api/tags
        # protocol against ``summarisation.endpoint`` — it is only
        # meaningful when the summarisation provider IS Ollama. For any
        # other provider the check consults an endpoint that is NOT the
        # configured backend, so a perfectly healthy backend hard-stopped
        # with "Model 'X' is not installed in Ollama" (reproduced live:
        # provider=llama.cpp serving the model while the legacy endpoint
        # key points at the llama.cpp server → /api/tags 404 → [] →
        # model_missing). Skip the check and let the provider call surface
        # the real error — the same semantics as the unreachable-Ollama
        # path below.
        from utils.settings import Settings

        _provider = (
            str(Settings().get("summarisation.provider", "ollama") or "ollama").strip().lower()
        )
        installed = self._fetch_installed_models(timeout=3.0) if _provider == "ollama" else None
        if installed is not None and model not in installed:
            avail = ", ".join(installed) if installed else "(none installed)"
            pull_hint = f"<br>👉 Fix: <code>ollama pull {model}</code>"
            alt_hint = (
                f"<br>Or pick one of the installed models above: <code>{avail}</code>"
                if installed
                else "<br>Or pull a model first: <code>ollama pull llama3.1:8b</code>"
            )
            return {
                "model_missing": True,
                "error_html": (
                    f"❌ Model '<b>{model}</b>' is not installed in Ollama.{pull_hint}{alt_hint}"
                ),
            }
        # If installed is None (Ollama unreachable / timed out), skip the
        # pre-flight and let the generate call surface the real error.

        results: list[str] = []
        total = len(inputs)
        for i, (stem, text) in enumerate(inputs):
            # Determine output path for this item.
            if is_multi:
                out_path_i = str(_P(out_folder) / f"{stem}_{quality}_summary{ext}")
            else:
                # Single paste: use the user-chosen path as-is, but if it's a
                # folder, fall back to auto-naming.
                if _P(out_path).is_dir():
                    out_path_i = str(_P(out_path) / f"{stem}_{quality}_summary{ext}")
                else:
                    out_path_i = out_path
                    # V11.67.0: if the user manually typed a file extension
                    # (e.g., .md), use THAT format — not the combo's resolved
                    # format. This prevents writing .docx binary data into a
                    # .md file (which makes it unreadable).
                    user_ext = _P(out_path).suffix.lower()
                    if user_ext in (".md", ".docx", ".pdf", ".txt"):
                        ext = user_ext

            # V11.20: bigger, bolder, eye-catching progress text (identical
            # HTML to the old inline version, now via the queued signal).
            if report is not None:
                report(
                    int(i * 100 / total) if total else 0,
                    (
                        f"<div style='font-size:15px; font-weight:600;'>"
                        f"🤖 Summarizing {i + 1}/{total}: <span style='color: var(--primary);'>{stem}</span>"
                        f"</div>"
                        f"<div style='font-size:12px; color: var(--muted-foreground); margin-top:2px;'>"
                        f"model: {model}  |  quality: {quality}  |  format: {ext}"
                        f"</div>"
                    ),
                )

            prompt, max_tokens = self._build_prompt(text, quality)
            # V13.25.0: Use _call_llm (delegates to llm_provider) instead of
            # _call_ollama (direct requests.post with no supervisor/retry).
            # V18.20.4.5 (W-b5): forward ``report`` so the streaming chunks
            # ride the queued progress signal instead of touching widgets.
            raw_response, err = self._call_llm(model, prompt, max_tokens, temp, report=report)
            if err:
                results.append(f"❌ {stem} → {err}")
                # On a model-level error (404, connection), bail out of the
                # whole batch — retrying the next file with the same broken
                # model is pointless.
                if "404" in err or "Cannot connect" in err or "timed out" in err:
                    break
                continue

            # V13.25.0: Parse the XML-tagged response into structured sections
            # using the core response_parser. This handles <executive_summary>,
            # <bullet_points>, <thorough_summary> tags, strips thinking blocks,
            # and falls back to plain-text parsing if the model didn't use XML.
            parsed = parse_response(raw_response, academic_rigor=False)
            exec_summary = parsed.get("executive_summary", "")
            bullet_points = parsed.get("bullet_points", [])
            thorough = parsed.get("thorough_summary", "")

            # Build a clean markdown document from the parsed sections.
            # For "fast" quality, skip the thorough summary to keep it short.
            md_parts = []
            if exec_summary:
                md_parts.append(f"## Executive Summary\n\n{exec_summary}")
            if bullet_points:
                bullets_md = "\n".join(f"- {b}" for b in bullet_points)
                md_parts.append(f"## Key Takeaways\n\n{bullets_md}")
            if thorough and quality != "fast":
                md_parts.append(f"## Detailed Summary\n\n{thorough}")

            summary_text = "\n\n---\n\n".join(md_parts) if md_parts else raw_response

            # V11.18: write via shared formatter (md/docx/pdf + optional Obsidian)
            ok, msg = write_output(
                summary_text,
                _P(out_path_i),
                fmt=ext,
                title=f"{stem} — {quality} summary",
                obsidian=obsidian,
                source_filename=f"{stem}.txt" if stem == "pasted" else f"{stem}.txt",
                quality=quality,
                model=model,
            )
            if ok:
                results.append(f"✅ {stem} → {_P(out_path_i).name} ({len(summary_text):,} chars)")
            else:
                results.append(f"⚠️ {stem} → {msg}")

        # V11.25: file arg for the success modal (computed here — pure file
        # checks; the finished handler just passes it through).
        if is_multi:
            file_arg = out_folder
        else:
            p = _P(out_path)
            file_arg = str(p) if p.exists() else str(p.parent)

        return {
            "results": results,
            "total": total,
            # V11.19 semantics (kept): only persist the model choice when
            # the user picked a concrete model — enforced in the finished
            # handler on the main thread.
            "persist_model": bool(model_data and model_data != "__default__"),
            "model": model,
            "file_arg": file_arg,
        }

    def _on_summarize_progress(self, pct: int, msg: str) -> None:
        # V18.20.4.5 (W-b5): main thread (queued signal) — safe to touch
        # widgets; no repaint hack needed.
        self.status_label.setText(msg)

    def _on_summarize_finished(self, result) -> None:
        # V18.20.4.5 (W-b5): main-thread completion — the old post-loop UI
        # block with identical strings, plus the model-missing pre-flight
        # branch (the combo refresh must run HERE, never in the worker).
        self.progress_bar.setVisible(False)
        result = result or {}

        if result.get("model_missing"):
            _err_html = result.get("error_html", "❌ Model not installed.")
            self.status_label.setText(_err_html)
            # Main-thread model refresh (touches the combo + status label).
            self._refresh_models()
            # V0.6.0 (S2 fix): _refresh_models ends by writing its own
            # reachability status ("Ollama is running but has no models…"),
            # which CLOBBERED the actionable error above within the same
            # handler — the user never saw why the run failed (reproduced
            # live). Re-assert the error after the refresh; the combo stays
            # refreshed either way.
            self.status_label.setText(_err_html)
            self.action_btn.setEnabled(True)
            self.action_btn.setText("Summarize")
            return

        results = result.get("results", [])
        total = result.get("total", 0)

        # V11.19: Only persist the model choice if the user picked a concrete
        # model (not "Default"). When "Default" is selected, we leave the
        # settings alone — the user's default configuration is authoritative.
        if result.get("persist_model"):
            from utils.settings import Settings

            s = Settings()
            s.set("summarisation.model", result.get("model"))
            s.save()

        # Build a summary status line.
        if total == 1:
            self.status_label.setText("<br>".join(results))
        else:
            self.status_label.setText(
                f"Done! {total} file(s) processed:<br><br>" + "<br>".join(results)
            )

        self.action_btn.setEnabled(True)
        self.action_btn.setText("Close")
        # V11.18: surface "Try Another File"
        self.again_btn.setVisible(True)

        # V11.25: success modal with "Try Another" + "Open File Location".
        _show_success_modal(
            self,
            "Σ Summarization Complete",
            "\n".join(results),
            file_path=result.get("file_arg"),
            on_try_another=self._on_try_another,
        )

    def _on_summarize_failed(self, err: str) -> None:
        # V18.20.4.5 (W-b5): the worker raised — surface on the main thread
        # and re-enable the button so the user can retry.
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ Error: {err}")
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Summarize")
