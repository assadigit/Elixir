"""Transcribe Service dialog (V18.20.4.6, P5 / O-b2 split).

TranscribeServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ now delegates the common
skeleton (title, file row, options container, output row, progress,
status, buttons) to the base and folds its copies of the base-provided
closeEvent guard + _emit_progress away; the media file picker, the
FOLDER output picker, the custom worker flow and the plain-text
progress handler stay as overrides (behavior the base does not
provide)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer

from controller import Controller

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model (core.llm.model_taxonomy is a leaf module — stdlib-only, no cycle).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
# V0.6.56: the live-log heartbeat cadence (core.transcribe.pipeline_log
# is a Qt-free stdlib-only leaf — no import cycle).
from core.transcribe.pipeline_log import HEARTBEAT_INTERVAL_MS
from core.system.timeouts import UI_PROBE_TIMEOUT_S
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
)

logger = logging.getLogger(__name__)

# V0.6.56: the single source of the LLM streaming status prefix — used
# by _do_transcribe's on_chunk lambda AND _on_progress's log sampler so
# the two can never drift apart (a drifted prefix would re-flood the
# live log with per-chunk lines).
_LLM_CHUNK_PREFIX = "📝 LLM is writing"


# ════════════════════════════════════════════════════════════════════════════
# V11.78.0: Transcribe Service — video/audio → text + Obsidian summary
# ════════════════════════════════════════════════════════════════════════════


class TranscribeServiceDialog(BaseServiceDialog):
    """V11.78.0: Transcribe Service — video/audio → text + Obsidian summary.

    Pipeline:
    1. Import video or audio file
    2. Extract audio (ffmpeg) if video
    3. Transcribe with faster-whisper (GPU-accelerated)
    4. Output raw transcript (with timestamps)
    5. Summarize with Ollama LLM → Obsidian-friendly markdown

    Model: faster-whisper (CTranslate2) — 4x faster than openai/whisper
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options, which needs llm_combo etc. to
        # attach to (the documented BaseServiceDialog subclassing recipe).
        # The base also initializes self._worker (its closeEvent guards it).
        super().__init__(
            controller, "🎙️ Transcribe Service", parent, accept_files=True, accept_text=False
        )
        # V0.6.10 (B17): this dialog's original geometry + plain progress
        # semantics (determinate 0-100 bar) — the base defaults differ.
        self.setMinimumSize(750, 650)
        self.progress_bar.setRange(0, 100)
        # V0.6.10 (B17): the base builds file_path_edit / out_path_edit and
        # wires the process button to _on_process with the label "Process";
        # this dialog's historical attribute names (file_edit / out_edit —
        # pinned by the e2e drive tests) and button label are restored as
        # aliases of the SAME widgets (single source of truth).
        self.file_edit = self.file_path_edit
        self.file_edit.setPlaceholderText(
            "Pick a video (.mp4, .mkv, .avi) or audio (.mp3, .wav, .m4a) file…"
        )
        self.out_edit = self.out_path_edit
        self.out_edit.setPlaceholderText("Choose output folder…")
        self.process_btn.setText("🎙️ Transcribe")
        # V0.6.56: the base's live-log toggle + panel are now this tool's
        # INTERNAL LOG CONTAINER (the house pattern — the packets tool
        # precedent). The operator ran a real video and waited 10 minutes
        # with no way to tell FROZEN from PROGRESSING; now the toggle stays
        # visible, every pipeline message lands in the log (see
        # _on_progress), and the heartbeat timer below keeps proving the
        # app is alive even while the engine is silent (whisper model
        # load / an LLM that fell back to CPU).
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat)
        self._run_started_ts = 0.0
        self._last_update_ts = 0.0
        # V0.6.57: the engine id of the CURRENT run ("transcribe_cpp" /
        # "faster_whisper") — the heartbeat hint is engine-aware, so a
        # silent transcribe.cpp run explains end-only printing + the [GPU]
        # lines instead of the LLM-on-CPU text (which misled the operator
        # on a raw-transcript-only run).
        self._run_engine = None
        self._last_status_msg = ""
        self._llm_chunk_counter = 0

        # Refresh models (same position as the pre-B17 __init__ tail).
        self._refresh_models()
        # V0.6.59: populate the GGUF model combo from the catalog's disk
        # scan (after _build_options created the combo — the V0.6.55
        # construction-order rule).
        self._refresh_cpp_models()
        # V0.6.45: set initial visibility of the summary model combo.
        self._on_output_check_changed()

    def _build_options(self, layout: QVBoxLayout) -> None:
        """V0.6.10 (B17): the transcription-specific option rows, folded
        into the base's options container (the base already built the
        description-style title + the file row + the output row)."""
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
            QPushButton as _QPB,
        )

        desc = _QL(
            "Import a video or audio file → get a raw transcript + "
            "an Obsidian-friendly summarized version. Uses "
            "transcribe.cpp (Vulkan GPU) or faster-whisper."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── Options ───────────────────────────────────────────────────
        # V0.6.40 (W-t2): Engine selector — faster-whisper (default) or
        # transcribe.cpp (Vulkan GPU, Whisper large-v3 GGUF).
        engine_row = _HL()
        engine_row.addWidget(_QL("Engine:"))
        self.engine_combo = _QCB()
        # V0.6.55 (P1): the combo order FLIPPED — transcribe.cpp is the
        # DEFAULT selection, matching the service default (V0.6.42's
        # decision: "transcribe.cpp is now the DEFAULT engine inside
        # transcribe_audio()") and the operator's Vulkan rig. The dialog
        # had silently kept faster-whisper first — dialog default and
        # service default disagreed.
        self.engine_combo.addItem("transcribe.cpp (Vulkan GPU)", "transcribe_cpp")
        self.engine_combo.addItem("faster-whisper (CTranslate2)", "faster_whisper")
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        engine_row.addWidget(self.engine_combo)
        engine_row.addStretch()
        layout.addLayout(engine_row)

        # V0.6.59: the GGUF model row — "I already downloaded whisper
        # large v3 from handy computer, so I just select the gguf model".
        # The combo lists every Whisper .gguf the catalog finds on disk
        # (the CLI exe's folder, C:\transcribe.cpp\models, the saved
        # model's folder, ~/Downloads — where a browser download lands)
        # with name · quant · size · header-verification, so picking the
        # downloaded model is ONE CLICK, not a browse. The 🔄 button
        # rescans; the 📁 Model button (V0.6.41, moved here from the
        # engine row) stays for one-off paths and refreshes the combo.
        cpp_model_row = _HL()
        cpp_model_row.addWidget(_QL("GGUF model:"))
        self.cpp_model_combo = _QCB()
        self.cpp_model_combo.setToolTip(
            "Whisper .gguf files found on disk (name · quant · size · header-verified).\n"
            "Selecting one saves it — the engine re-verifies the file before every run.\n"
            "Models: huggingface.co/handy-computer (e.g. whisper-large-v3-Q8_0.gguf)"
        )
        self.cpp_model_combo.currentIndexChanged.connect(self._on_cpp_model_selected)
        cpp_model_row.addWidget(self.cpp_model_combo, 1)
        self.cpp_model_refresh_btn = _QPB("🔄")
        self.cpp_model_refresh_btn.setToolTip("Rescan disk for Whisper .gguf models")
        self.cpp_model_refresh_btn.clicked.connect(self._refresh_cpp_models)
        cpp_model_row.addWidget(self.cpp_model_refresh_btn)
        # V0.6.60: the downloader -- when the model is NOT on disk yet,
        # "⬇ Get models" closes the loop inside the app: the curated
        # handy-computer catalog (live-verified), progress + resume,
        # GGUF-header verification, auto-select on arrival. The
        # placeholder text in _refresh_cpp_models points here when the
        # disk has no model at all.
        self.cpp_model_download_btn = _QPB("⬇ Get models")
        self.cpp_model_download_btn.setObjectName("Compact")
        self.cpp_model_download_btn.setToolTip(
            "Download a Whisper GGUF model (handy-computer's Hugging Face "
            "repos) — with progress + resume; the downloaded file is "
            "verified from its own GGUF header and selected automatically"
        )
        self.cpp_model_download_btn.clicked.connect(self._open_model_downloader)
        cpp_model_row.addWidget(self.cpp_model_download_btn)
        self.cpp_model_browse_btn = _QPB("📁 Model")
        self.cpp_model_browse_btn.setToolTip("Browse for a Whisper .gguf model file")
        self.cpp_model_browse_btn.clicked.connect(self._browse_cpp_model)
        cpp_model_row.addWidget(self.cpp_model_browse_btn)
        cpp_model_row.addStretch()
        _cpp_row_widget = QWidget()
        _cpp_row_widget.setLayout(cpp_model_row)
        layout.addWidget(_cpp_row_widget)
        self.cpp_model_row = _cpp_row_widget

        # V0.6.39 (W-s1): Whisper model — auto-detect + custom-path browse.
        # The combo shows the standard faster-whisper model sizes, PLUS any
        # locally-downloaded models found via auto-detection. A "Browse"
        # button lets the operator pinpoint a custom model folder on disk.
        model_row = _HL()
        self.whisper_model_label = _QL("Whisper model:")
        model_row.addWidget(self.whisper_model_label)
        self.whisper_combo = _QCB()
        self.whisper_combo.addItem("small (recommended — good balance)", "small")
        self.whisper_combo.addItem("tiny (fastest — quick drafts)", "tiny")
        self.whisper_combo.addItem("base (fast — meetings)", "base")
        self.whisper_combo.addItem("medium (high accuracy)", "medium")
        self.whisper_combo.addItem("large-v3 (best accuracy — slow)", "large-v3")
        model_row.addWidget(self.whisper_combo)
        # V0.6.39: Browse button for custom whisper model path.
        self.whisper_browse_btn = _QPB("📁")
        self.whisper_browse_btn.setToolTip("Browse for a custom Whisper model folder on disk")
        self.whisper_browse_btn.clicked.connect(self._browse_whisper_model)
        model_row.addWidget(self.whisper_browse_btn)
        model_row.addStretch()
        layout.addLayout(model_row)

        # V0.6.55 (Task 9 review BLOCKER fix): apply the initial visibility
        # for the DEFAULT selection (transcribe.cpp → the whisper model row
        # hidden) — the _on_engine_changed slot only fires on index CHANGE,
        # so the first paint needs the explicit call. The call MUST stay
        # BELOW the whisper_combo / whisper_browse_btn creation (the slot
        # touches both): calling it from the engine-row block crashed the
        # dialog's construction with AttributeError (the exact
        # V0.6.53-NameError failure class the redesign was meant to kill —
        # caught by the fresh-eyes review because this sandbox has no
        # PySide6 and the AST pins only checked the call EXISTS, not WHERE).
        # V0.6.59: the same now holds for cpp_model_combo / cpp_model_row /
        # cpp_model_browse_btn — every widget the slot touches is created
        # above this line (the extended pin enforces it).
        self._on_engine_changed()

        # V0.6.39 (W-s2): LLM model — auto-detect BOTH Ollama and llama.cpp.
        # The label changed from "Summary model (Ollama):" to
        # "Summary model:" because the backend auto-detects which LLM
        # is running (the decide_llamacpp_first policy). The refresh
        # button now probes BOTH backends.
        llm_row = _HL()
        llm_row.addWidget(_QL("Summary model:"))
        self.llm_combo = _QCB()
        self.llm_combo.setEditable(True)
        # V0.6.41: DON'T pre-fill with RIG_FALLBACK_MODEL — it's a hardcoded
        # model name that may not exist on the operator's machine. Leave
        # empty; _refresh_models() (called at the end of __init__) will
        # auto-detect whatever is actually running.
        llm_row.addWidget(self.llm_combo, 1)
        self.refresh_btn = _QPB("🔄")
        self.refresh_btn.setToolTip("Refresh LLM models (auto-detects Ollama + llama.cpp)")
        self.refresh_btn.clicked.connect(self._refresh_models)
        llm_row.addWidget(self.refresh_btn)
        # V0.6.55 (P1c): the one-click LLM health check — resolves the
        # backend (llama.cpp port auto-detection 8080/8000/9931), probes
        # a real tiny generation, and measures its speed: a CPU fallback
        # (the n_gpu_layers GPU-fit failure) is reported with the
        # actionable restart hint instead of surfacing later as a
        # 30-minute frozen "Summarizing..." label.
        self.llm_test_btn = _QPB("\U0001f50c Test")
        self.llm_test_btn.setToolTip(
            "Test the LLM connection: detects the backend (llama.cpp ports "
            "8080/8000/9931 are auto-probed + Ollama), checks that it "
            "responds, and measures generation speed \u2014 warns about the "
            "VRAM/CPU fallback that makes summaries 10-30x slower."
        )
        self.llm_test_btn.clicked.connect(self._on_test_llm)
        llm_row.addWidget(self.llm_test_btn)
        layout.addLayout(llm_row)

        # Checkboxes
        self.cb_raw = _QChB("Raw transcript (with timestamps)")
        self.cb_raw.setChecked(True)
        self.cb_raw.stateChanged.connect(self._on_output_check_changed)
        layout.addWidget(self.cb_raw)

        self.cb_summary = _QChB("Summary (core concepts + key takeaways)")
        self.cb_summary.setChecked(True)
        self.cb_summary.stateChanged.connect(self._on_output_check_changed)
        layout.addWidget(self.cb_summary)

        # V0.6.43: third output — tutorial/educational guide.
        self.cb_tutorial = _QChB("Tutorial guide (educational / tips & tricks)")
        self.cb_tutorial.setChecked(False)
        self.cb_tutorial.stateChanged.connect(self._on_output_check_changed)
        layout.addWidget(self.cb_tutorial)

        # ── Process button ────────────────────────────────────────────
        # V13.31.0 (#7): Live Transcribe sub-tool
        live_row = _HL()
        live_row.addStretch()
        self.live_btn = _QPB("🎤 Live Transcribe (Microphone)")
        self.live_btn.setObjectName("Compact")
        self.live_btn.setToolTip(
            "Open the live microphone transcription tool — "
            "records audio and transcribes in real-time using Whisper"
        )
        self.live_btn.clicked.connect(self._open_live_transcribe)
        live_row.addWidget(self.live_btn)
        layout.addLayout(live_row)

    # V0.6.10 (B17): the closeEvent guard (identical to the base's —
    # _confirm_close_with_running_worker(self, self._worker)) and
    # _emit_progress are now INHERITED from BaseServiceDialog; the
    # pre-B17 copies were byte-equivalent and were deleted.

    def _on_engine_changed(self):
        """V0.6.40 (W-t2) + V0.6.59: toggle the model rows based on the
        selected engine. transcribe.cpp gets the GGUF model row (combo +
        rescan + browse); faster-whisper gets its model-size row. The
        faster-whisper row's LABEL is now hidden too (it used to stay
        visible with hidden widgets — a dangling label)."""
        engine = self.engine_combo.currentData()
        is_faster_whisper = engine == "faster_whisper"
        # Show/hide the faster-whisper model row (label + combo + browse).
        self.whisper_model_label.setVisible(is_faster_whisper)
        self.whisper_combo.setVisible(is_faster_whisper)
        self.whisper_browse_btn.setVisible(is_faster_whisper)
        # Show/hide the transcribe.cpp GGUF model row (whole container).
        self.cpp_model_row.setVisible(not is_faster_whisper)

    def _on_output_check_changed(self):
        """V0.6.45: hide the Summary model combo + refresh button when
        the user only wants the raw transcript (no summary or tutorial).
        The LLM model is only used for summary + tutorial — showing it
        when neither is checked is confusing."""
        needs_llm = self.cb_summary.isChecked() or (
            hasattr(self, "cb_tutorial") and self.cb_tutorial.isChecked()
        )
        self.llm_combo.setVisible(needs_llm)
        self.refresh_btn.setVisible(needs_llm)
        # V0.6.55 (P1c): the Test button follows the same rule — it
        # checks the backend those outputs depend on.
        if hasattr(self, "llm_test_btn"):
            self.llm_test_btn.setVisible(needs_llm)

    def _browse_cpp_model(self):
        """V0.6.41: Browse for the transcribe.cpp Whisper model file
        (.gguf). The selected path is saved to the app's settings
        (transcribe.transcribe_cpp_model) so the engine picks it up.
        V0.6.59: the filter puts .gguf first (transcribe-cli.exe loads
        GGUF — a legacy ggml-*.bin picked through the old *.pt-including
        filter died minutes into the run), and the GGUF combo is
        refreshed so the picked model shows up selected + verified."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick transcribe.cpp Whisper model file",
            "",
            "Whisper GGUF models (*.gguf);;Legacy ggml models (*.bin);;All files (*.*)",
        )
        if path:
            from utils.settings import Settings

            s = Settings()
            s.set("transcribe.transcribe_cpp_model", path)
            self.status_label.setText(
                f"✅ Model set: {Path(path).name} (saved to settings)"
            )
            self._refresh_cpp_models()

    def _on_cpp_model_selected(self, index: int):
        """V0.6.59: picking a GGUF from the combo saves it — the
        "just select the gguf model" flow. The engine re-verifies the
        file's header before every run, so a wrong pick fails in
        seconds with the fix, not minutes into the run."""
        path = self.cpp_model_combo.currentData() if index >= 0 else None
        if not path:
            return
        try:
            from utils.settings import Settings

            s = Settings()
            s.set("transcribe.transcribe_cpp_model", str(path))
            self.status_label.setText(
                f"✅ Model set: {Path(path).name} (saved to settings)"
            )
        except Exception:
            self.status_label.setText(
                f"⚠️ Model selected: {Path(path).name} (could not save setting)"
            )

    def _refresh_cpp_models(self):
        """V0.6.59: repopulate the GGUF combo from disk — the catalog's
        scan (the CLI exe's folder + its models/, C:\transcribe.cpp\
        models, the saved model's folder, ~/Downloads). Every entry
        shows name · quant · size · header-verification; the saved
        setting (even if outside the scan dirs) is listed first and
        selected. Best-effort everywhere: a settings/scan failure
        leaves the combo empty, never crashes the dialog."""
        self.cpp_model_combo.blockSignals(True)
        self.cpp_model_combo.clear()
        # V0.6.59 review fix: settings values are coerced to str — a
        # corrupt setting (int/list/dict) must never raise in Path(...)
        # at dialog open (the V0.6.53/55 construction-crash class).
        current = None
        exe = None
        try:
            from utils.settings import Settings

            s = Settings()
            _cur = s.get("transcribe.transcribe_cpp_model", None)
            _exe = s.get("transcribe.transcribe_cpp_exe", None)
            current = str(_cur) if _cur else None
            exe = str(_exe) if _exe else None
        except Exception:
            pass
        items: list[tuple[str, str, str]] = []
        if current and Path(current).exists():  # current is str-coerced above
            try:
                from core.transcribe.model_catalog import (
                    describe_model_file,
                    format_model_display,
                    format_model_tooltip,
                )

                _info = describe_model_file(current)
                items.append(
                    (
                        format_model_display(_info),
                        str(current),
                        format_model_tooltip(_info),
                    )
                )
            except Exception:
                items.append(
                    (
                        f"{Path(current).name} (saved setting)",
                        str(current),
                        f"{Path(current).name} (saved setting)\nFile: {current}",
                    )
                )
        try:
            from core.transcribe import model_catalog
            from core.transcribe.transcribe_cpp_engine import DEFAULT_TRANSCRIBE_CPP_EXE

            found = model_catalog.scan_model_dirs(
                model_catalog.model_search_dirs(
                    exe_path=exe or DEFAULT_TRANSCRIBE_CPP_EXE, saved_model=current
                )
            )
            known = {p for _, p, _ in items}
            for info in found:
                if info["path"] not in known:
                    items.append(
                        (
                            model_catalog.format_model_display(info),
                            info["path"],
                            model_catalog.format_model_tooltip(info),
                        )
                    )
                    known.add(info["path"])
        except Exception:
            pass
        select = -1
        for display, path, tooltip in items:
            self.cpp_model_combo.addItem(display, path)
            # V0.6.60: every entry carries the catalog's full facts as
            # its tooltip -- what the file's OWN header proved (name /
            # params / quant / size / path), not just the one-liner.
            self.cpp_model_combo.setItemData(
                self.cpp_model_combo.count() - 1,
                tooltip,
                Qt.ItemDataRole.ToolTipRole,
            )
            if current and path == str(current):
                select = self.cpp_model_combo.count() - 1
        if select < 0 and items:
            select = 0
        if select >= 0:
            self.cpp_model_combo.setCurrentIndex(select)
        elif not items:
            self.cpp_model_combo.addItem(
                "(no Whisper .gguf found — ⬇ Get models, or 📁 Model to browse)", None
            )
        self.cpp_model_combo.blockSignals(False)

    def _cpp_model_display(self) -> str | None:
        """V0.6.59: the selected GGUF's file name for the run header.
        The V0.6.57 gap: transcribe.cpp runs logged NO model line (the
        whisper_combo's size is meaningless for the GGUF engine) — now
        the header carries the actual selected model file."""
        idx = self.cpp_model_combo.currentIndex()
        if idx < 0:
            return None
        path = self.cpp_model_combo.itemData(idx)
        return Path(path).name if path else None

    # ── V0.6.60: the model downloader entry point ─────────────────────

    def _open_model_downloader(self):
        """V0.6.60: open the Get-models dialog (the curated
        handy-computer catalog, progress + resume, GGUF-header
        verification). A successful download calls back into
        _on_model_installed, which saves the setting + selects the
        file in the GGUF combo -- the download → selected one-flow."""
        from ui_qt.views.service_dialogs.model_download_dialog import (
            ModelDownloadDialog,
        )

        dlg = ModelDownloadDialog(self, on_installed=self._on_model_installed)
        dlg.exec()

    def _on_model_installed(self, path: str):
        """V0.6.60: a model came out of the downloader: save the
        setting (the 'download → selected' one-click flow), refresh the
        combo (it lists the saved entry first and selects it), and put
        the event in the live log (the running record)."""
        try:
            from utils.settings import Settings

            Settings().set("transcribe.transcribe_cpp_model", str(path))
        except Exception:
            logger.debug("best-effort settings save failed", exc_info=True)
        try:
            self._refresh_cpp_models()
        except Exception:
            logger.debug("best-effort combo refresh failed", exc_info=True)
        self.status_label.setText(
            f"✅ Model downloaded: {Path(path).name} (selected)"
        )
        try:
            self._append_live_log(f"⬇ Model downloaded: {Path(path).name} (selected)")
        except Exception:
            pass

    def _browse_whisper_model(self):
        """V0.6.39 (W-s1): Browse for a custom Whisper model folder on disk.

        faster-whisper models are directories containing model.bin +
        config.json + tokenizer files. The operator may have them in a
        non-standard location. This lets them pick the folder; the path
        becomes the whisper_combo's currentData (used as model_size
        when it's a path, not a known size name).
        """
        folder = QFileDialog.getExistingDirectory(
            self, "Pick Whisper model folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            # Add the custom path to the combo (if not already there).
            display = f"📁 {Path(folder).name} (custom path)"
            idx = self.whisper_combo.findData(folder)
            if idx < 0:
                self.whisper_combo.addItem(display, folder)
                idx = self.whisper_combo.count() - 1
            self.whisper_combo.setCurrentIndex(idx)

    def _refresh_models(self):
        """V0.6.39 (W-s2): Fetch LLM models — auto-detect BOTH Ollama
        and llama.cpp. The backend already uses decide_llamacpp_first
        to route; the UI now reflects this by probing BOTH.

        V0.6.8 (audit B5): routed through utils.network.list_ollama_models
        (safe_ollama_request → proxy-proof) — was a bare requests.get that
        broke on machines with HTTP_PROXY set.
        """
        from utils.network import list_ollama_models
        from utils.settings import Settings

        s = Settings()
        current = self.llm_combo.currentText()
        self.llm_combo.clear()
        found_any = False

        # ── Probe llama.cpp first (the decide_llamacpp_first policy
        # prefers it when it's running). ──
        try:
            from core.llm.local_fallback import decide_llamacpp_first

            _decision = decide_llamacpp_first(s, "ollama")
            if _decision.use_llamacpp:
                # llama.cpp is running — list its models.
                from core.llm.llamacpp_provider import list_llamacpp_models

                base = _decision.base_url
                api_key = _decision.api_key
                models = list_llamacpp_models(base, api_key)
                for m in models:
                    self.llm_combo.addItem(f"🦙 {m} (llama.cpp)")
                    found_any = True
                if found_any:
                    self.status_label.setText(
                        f"🦙 llama.cpp detected at {base} (model '{_decision.model}')"
                    )
        except Exception:
            logger.debug("best-effort llama.cpp probe failed", exc_info=True)

        # ── Probe Ollama (the always-on default). ──
        try:
            ollama_url = s.get("summarisation.ollama_url", "http://localhost:11434")
            models = [m for m in list_ollama_models(ollama_url, timeout=UI_PROBE_TIMEOUT_S) if m]
            for m in models:
                # Don't duplicate if llama.cpp already listed it.
                display = f"🦙 {m} (Ollama)"
                if self.llm_combo.findText(display) < 0:
                    self.llm_combo.addItem(display)
                    found_any = True
            if models and not found_any:
                self.status_label.setText(f"🦙 Ollama detected at {ollama_url}")
        except Exception:
            logger.debug("best-effort Ollama probe failed", exc_info=True)

        # V0.6.41: DON'T fallback to RIG_FALLBACK_MODEL — it's a hardcoded
        # model name that may not exist on the operator's machine. Leave
        # the combo empty so the operator can type a model name manually
        # or start their LLM and click 🔄.
        if not found_any:
            self.llm_combo.addItem("")
            self.status_label.setText(
                "⚠️ No LLM detected. Start Ollama or llama-server, then click 🔄."
            )

        # Restore the previously selected model if still present.
        idx = self.llm_combo.findText(current)
        if idx >= 0:
            self.llm_combo.setCurrentIndex(idx)
        elif self.llm_combo.count() > 0:
            self.llm_combo.setCurrentIndex(0)

    def _pick_file(self):
        # V0.6.10 (B17): override — the base's generic single-file picker
        # has no media filter; this one pins the video/audio families.
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick video or audio file",
            "",
            "Media files (*.mp4 *.mkv *.avi *.mov *.mp3 *.wav *.m4a *.flac *.ogg *.webm);;"
            "Video (*.mp4 *.mkv *.avi *.mov *.webm);;"
            "Audio (*.mp3 *.wav *.m4a *.flac *.ogg);;"
            "All files (*.*)",
        )
        if path:
            self.file_edit.setText(path)

    def _pick_output(self):
        # V0.6.10 (B17): override — transcription outputs are a FOLDER
        # (raw transcript + summary side by side), not a single file; the
        # base's file-save _pick_output does not fit (the OCR precedent
        # for folder-picking overrides).
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _open_live_transcribe(self):
        """V13.31.0 (#7): Open the live microphone transcription dialog."""
        from ui_qt.views.service_dialogs.live_transcribe import LiveTranscribeDialog

        dlg = LiveTranscribeDialog(self)
        dlg.exec()

    # ── V0.6.55 (P1c): the one-click LLM health check ──────────────────

    def _on_test_llm(self):
        """The 🔌 Test button: run check_llm_for_transcribe on a WORKER
        thread (the probe blocks for seconds — the V0.6.54 pattern of
        never blocking the UI thread) and render the result when it
        lands. The check resolves the backend (llama.cpp ports
        8080/8000/9931 auto-probed + Ollama), probes a tiny REAL
        generation, and measures its speed — the n_gpu_layers CPU
        fallback shows up here with its fix instead of as a 30-minute
        frozen summary later."""
        self.llm_test_btn.setEnabled(False)
        self.status_label.setText("🔌 Testing LLM connection...")
        # V0.6.56: the test also lands in the live log so the tool's
        # running record shows what was checked and when.
        self._append_live_log("🔌 Testing LLM connection...")

        def _work():
            from core.transcribe.llm_check import check_llm_for_transcribe
            from utils.settings import Settings

            s = Settings()
            ollama_url = (
                s.get_ollama_url()
                if hasattr(s, "get_ollama_url")
                else s.get("summarisation.ollama_url", "http://localhost:11434")
            )
            return check_llm_for_transcribe(s, ollama_url=ollama_url)

        # A SEPARATE worker handle: the transcription worker may be
        # running (the closeEvent guards self._worker); the probe must
        # not disturb it, and auto-deletes after finishing.
        self._llm_test_worker = SimpleWorker(_work)
        self._llm_test_worker.finished.connect(self._on_test_llm_done)
        self._llm_test_worker.failed.connect(self._on_test_llm_failed)
        self._llm_test_worker.start()

    def _on_test_llm_done(self, result: dict):
        """Render the health check: persist an auto-detected port (the
        operator is told, one click fixes every future run), then show
        the verdict — healthy (info box) / CPU-fallback suspicion
        (warning — the n_gpu_layers guidance) / unreachable (critical)."""
        self.llm_test_btn.setEnabled(True)
        if not isinstance(result, dict):
            self.status_label.setText("🔌 LLM test: unexpected result")
            return

        if result.get("save_url"):
            try:
                from utils.settings import Settings

                Settings().set("summarisation.llamacpp_base_url", result["save_url"])
            except Exception:
                logger.debug("best-effort settings save failed", exc_info=True)

        first_line = result.get("message", "").splitlines()[0] if result.get("message") else ""
        self.status_label.setText(f"🔌 {first_line}")
        # V0.6.56: the verdict is part of the running record (the dialog
        # box disappears; the log line stays for the paste-back).
        self._append_live_log(f"🔌 LLM test: {first_line}")

        level = result.get("level", "info")
        if level == "slow-cpu-fallback-suspected":
            QMessageBox.warning(
                self, "⚠️ LLM Responds — but VERY Slowly", result.get("message", "")
            )
        elif not result.get("ok"):
            QMessageBox.critical(self, "❌ LLM Unreachable", result.get("message", ""))
        else:
            QMessageBox.information(self, "✅ LLM OK", result.get("message", ""))

    def _on_test_llm_failed(self, error_msg):
        """The worker itself exploded (never expected — the check never
        raises) — still re-enable the button and show the reason."""
        self.llm_test_btn.setEnabled(True)
        self.status_label.setText(f"❌ LLM test failed: {error_msg}")
        QMessageBox.warning(self, "⚠️ LLM Test Failed", str(error_msg))

    def _on_process(self):
        # V0.6.10 (B17): kept override — the base's _on_process validates a
        # generic text/file input and spawns SimpleWorker(self._process, …);
        # this dialog's contract is a media-file existence check, its own
        # options dict, button-label swap (⏳ Transcribing…) and the
        # _on_done/_on_failed completion pair (no base-equivalent flow).
        filepath = self.file_edit.text().strip()
        if not filepath or not Path(filepath).exists():
            QMessageBox.warning(self, "No file", "Please pick a valid video or audio file.")
            return
        out_folder = self.out_edit.text().strip()
        if not out_folder:
            QMessageBox.warning(self, "No output", "Please choose an output folder.")
            return

        self.process_btn.setEnabled(False)
        self.process_btn.setText("⏳ Transcribing...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("🎙️ Starting transcription...")

        # V0.6.56: the internal log container — clear it, auto-open it
        # (the packets-tool precedent: the operator should never have to
        # FIND the log while a run is in flight), log the run header so
        # the configuration is on record, and start the heartbeat BEFORE
        # the worker exists so the whole worker lifetime is covered.
        from core.transcribe.pipeline_log import format_run_header

        self.live_log.clear()
        if not self._log_toggle_btn.isChecked():
            self._log_toggle_btn.setChecked(True)
            self._toggle_live_log(True)
        for _header_line in format_run_header(
            filepath=filepath,
            engine=self.engine_combo.currentText(),
            # The whisper_combo holds the FASTER-WHISPER model size;
            # the transcribe.cpp engine gets the SELECTED GGUF's file
            # name instead (V0.6.59 — closing the V0.6.57 gap where cpp
            # runs logged no model line at all).
            whisper_model=self.whisper_combo.currentData()
            if self.engine_combo.currentData() == "faster_whisper"
            else self._cpp_model_display(),
            llm_model=self.llm_combo.currentText().strip(),
            save_raw=self.cb_raw.isChecked(),
            save_summary=self.cb_summary.isChecked(),
            save_tutorial=self.cb_tutorial.isChecked()
            if hasattr(self, "cb_tutorial")
            else False,
        ):
            self._append_live_log(_header_line)
        self._append_live_log("🎙️ Starting transcription...")
        self._run_started_ts = time.time()
        self._last_update_ts = self._run_started_ts
        self._last_status_msg = "starting"
        # V0.6.57: capture the engine BEFORE the worker exists (the
        # heartbeat needs it 15s into the run; the combo is also about
        # to be irrelevant mid-run).
        self._run_engine = self.engine_combo.currentData()
        self._llm_chunk_counter = 0
        self._heartbeat_timer.start()

        options = {
            "filepath": filepath,
            "output_folder": out_folder,
            "engine": self.engine_combo.currentData(),
            "whisper_model": self.whisper_combo.currentData(),
            "llm_model": self.llm_combo.currentText().strip(),
            "save_raw": self.cb_raw.isChecked(),
            "save_summary": self.cb_summary.isChecked(),
            "save_tutorial": self.cb_tutorial.isChecked() if hasattr(self, "cb_tutorial") else False,
        }

        def _work():
            return self._do_transcribe(options)

        self._worker = SimpleWorker(_work)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _do_transcribe(self, options: dict) -> dict:
        """Run the full transcription pipeline."""
        from core.transcribe.transcribe_service import (
            extract_audio_from_video,
            format_transcript_with_timestamps,
            summarize_transcript,
            summarize_transcript_combined,
            transcribe_audio,
        )
        from utils.settings import Settings

        filepath = options["filepath"]
        out_folder = Path(options["output_folder"])
        out_folder.mkdir(parents=True, exist_ok=True)
        whisper_model = options["whisper_model"]
        llm_model = options["llm_model"]
        save_raw = options["save_raw"]
        save_summary = options["save_summary"]
        save_tutorial = options.get("save_tutorial", False)

        file_stem = Path(filepath).stem
        ext = Path(filepath).suffix.lower()
        is_video = ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")

        s = Settings()
        # V0.6.0 (T2): resolve the endpoint through the canonical
        # ``get_ollama_url()`` (5-key priority, settings.py) instead of the
        # single legacy ``summarisation.ollama_url`` key — the value is
        # forwarded to ``summarize_transcript``, which now honors it.
        ollama_url = (
            s.get_ollama_url()
            if hasattr(s, "get_ollama_url")
            else s.get("summarisation.ollama_url", "http://localhost:11434")
        )

        results = {"raw_path": None, "summary_path": None, "tutorial_path": None, "error": None}

        # Step 1: Extract audio if video
        audio_path = filepath
        if is_video:
            self._emit_progress(5, "🎬 Extracting audio from video...")
            temp_audio = str(out_folder / f"{file_stem}_audio.wav")
            if not extract_audio_from_video(
                filepath,
                temp_audio,
                log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
            ):
                results["error"] = "Failed to extract audio from video. Is ffmpeg installed?"
                return results
            audio_path = temp_audio

        # Step 2: Transcribe (V0.6.40: dispatch to selected engine; V0.6.55:
        # the fallback default follows the service's V0.6.42 decision —
        # transcribe_cpp, the Vulkan engine the rig actually uses).
        engine = options.get("engine", "transcribe_cpp")
        if engine == "transcribe_cpp":
            self._emit_progress(10, "🎙️ Transcribing with transcribe.cpp (Vulkan GPU)...")
            from core.transcribe.transcribe_cpp_engine import transcribe_with_cpp

            transcribe_result = transcribe_with_cpp(
                audio_path,
                language=None,
                log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                progress_callback=lambda pct, msg: self._emit_progress(pct, msg),
            )
        else:
            self._emit_progress(10, f"🎙️ Loading whisper model '{whisper_model}'...")
            transcribe_result = transcribe_audio(
                audio_path,
                model_size=whisper_model,
                log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                progress_callback=lambda pct, msg: self._emit_progress(pct, msg),
            )

        # V0.6.54: fix the NameError introduced in V0.6.53 — the variable was
        # renamed to ``_extracted_text`` for the log line but the summarize
        # calls below still referenced the old ``_transcript_text`` name,
        # raising ``NameError: name '_transcript_text' is not defined`` the
        # moment Step 4 (Summarize) ran — so the raw transcript was saved
        # (Step 3) but no summary / tutorial ever appeared. Single source of
        # truth: ``_extracted_text`` holds the plain-text transcript that
        # gets forwarded to the LLM (and the timestamped ``raw_text`` is only
        # used for the saved raw-transcript file).
        _extracted_text = transcribe_result.get("text", "")
        _extracted_segs = len(transcribe_result.get("segments", []))
        self._emit_progress(-1, f"[INFO] Extracted {len(_extracted_text)} chars, {_extracted_segs} segments, language={transcribe_result.get('language', 'None')}")

        if "error" in transcribe_result:
            results["error"] = transcribe_result["error"]
            return results

        # Step 3: Save raw transcript
        if save_raw:
            self._emit_progress(90, "💾 Saving raw transcript...")
            raw_text = format_transcript_with_timestamps(transcribe_result["segments"])
            raw_path = out_folder / f"{file_stem}_transcript.md"
            raw_path.write_text(
                f"# Transcript: {file_stem}\n\n"
                f"**Duration:** {transcribe_result['duration']:.1f}s\n"
                f"**Language:** {transcribe_result['language']}\n\n"
                f"---\n\n{raw_text}\n",
                encoding="utf-8",
            )
            results["raw_path"] = str(raw_path)

        # Step 4+5: the LLM outputs (V0.6.55 redesign of the old
        # sequential Step 4 summary → Step 5 tutorial two-round-trip):
        # - BOTH outputs requested → ONE combined round trip (P3); a
        #   failed split falls back to the separate tutorial call
        #   (correctness over speed — the service signals it).
        # - on_chunk streams the growing generation to the status label
        #   (P4) — no more frozen "Summarizing..." for 10+ minutes.
        # - failures raise the structured TranscribeError family (P5)
        #   and land in results["error"] as stage + message + fix.
        from core.transcribe.errors import TranscribeError, TranscribePipelineError

        summary_text = None
        tutorial_text = None

        _log = lambda msg, level="INFO": self._emit_progress(-1, msg)  # noqa: E731
        _prog = lambda pct, msg: self._emit_progress(pct, msg)  # noqa: E731
        _on_chunk = lambda partial: self._emit_progress(  # noqa: E731
            -1, f"{_LLM_CHUNK_PREFIX}… {len(partial):,} chars so far"
        )

        try:
            if save_summary and save_tutorial:
                self._emit_progress(92, "📝 Generating notes + tutorial (one LLM call)...")
                combined = summarize_transcript_combined(
                    _extracted_text,
                    model=llm_model,
                    ollama_url=ollama_url,
                    log_callback=_log,
                    progress_callback=_prog,
                    on_chunk=_on_chunk,
                )
                summary_text = combined["summary"]
                tutorial_text = combined["tutorial"]
                if not combined["split_ok"]:
                    # The model ignored the split marker — generate the
                    # tutorial separately (the pre-V0.6.55 behavior, now
                    # only the CORRECTNESS net instead of the default).
                    self._emit_progress(
                        95, "📚 Split failed — generating the tutorial separately..."
                    )
                    tutorial_text = summarize_transcript(
                        _extracted_text,
                        model=llm_model,
                        ollama_url=ollama_url,
                        log_callback=_log,
                        progress_callback=_prog,
                        output_type="tutorial",
                        on_chunk=_on_chunk,
                    )
            elif save_summary:
                self._emit_progress(92, "📝 Summarizing with LLM...")
                summary_text = summarize_transcript(
                    _extracted_text,
                    model=llm_model,
                    ollama_url=ollama_url,
                    log_callback=_log,
                    progress_callback=_prog,
                    on_chunk=_on_chunk,
                )
            elif save_tutorial:
                self._emit_progress(92, "📚 Generating tutorial guide with LLM...")
                tutorial_text = summarize_transcript(
                    _extracted_text,
                    model=llm_model,
                    ollama_url=ollama_url,
                    log_callback=_log,
                    progress_callback=_prog,
                    output_type="tutorial",
                    on_chunk=_on_chunk,
                )
        except TranscribeError as e:
            # P5: structured failure — stage + message + fix, rendered
            # friendly; non-fatal when the raw transcript is already
            # saved (the V0.6.54 completion-dialog contract).
            results["error"] = str(e)
            return results
        except Exception as e:  # noqa: BLE001 — the V0.6.53 NameError class of surprise
            logger.exception("Transcribe pipeline: unexpected error in the LLM step")
            results["error"] = str(
                TranscribePipelineError(
                    f"Unexpected internal error while generating the LLM output: {e}"
                )
            )
            return results

        if summary_text:
            self._emit_progress(94, "💾 Saving summary...")
            summary_path = out_folder / f"{file_stem}_summary.md"
            summary_path.write_text(summary_text, encoding="utf-8")
            results["summary_path"] = str(summary_path)

        if tutorial_text:
            self._emit_progress(97, "📚 Saving tutorial guide...")
            tutorial_path = out_folder / f"{file_stem}_tutorial.md"
            tutorial_path.write_text(tutorial_text, encoding="utf-8")
            results["tutorial_path"] = str(tutorial_path)

        # Clean up temp audio
        if is_video and Path(audio_path).exists():
            try:
                Path(audio_path).unlink()
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

        self._emit_progress(100, "✅ Done!")
        return results

    def _on_progress(self, pct: int, msg: str):
        # V0.6.10 (B17): kept override — the base's _on_progress wraps the
        # status text in HTML + appends to the live log; this dialog's
        # contract (pinned by the e2e drive tests) is plain-text status
        # and a determinate 0-100 bar.
        # V0.6.56: every pipeline message ALSO lands in the live log —
        # the internal log container answers "frozen or progressing?"
        # from the timestamps — and resets the heartbeat gap clock.
        # (The streaming "📝 LLM is writing" lines are sampled every
        # 10th in the LOG — the status label still updates on every
        # chunk — so a long generation doesn't bury the real events.)
        if pct >= 0:
            self.progress_bar.setValue(pct)
        self.status_label.setText(msg)
        if msg.startswith(_LLM_CHUNK_PREFIX):
            self._llm_chunk_counter += 1
            if self._llm_chunk_counter % 10 == 1:
                self._append_live_log(msg)
        else:
            self._append_live_log(msg)
        self._last_update_ts = time.time()
        self._last_status_msg = msg

    def _on_heartbeat(self):
        """V0.6.56: the 15s heartbeat — while a run is alive, prove the
        app is responsive and MEASURE the engine's silence: the line
        carries the elapsed time plus how long since the last pipeline
        update, so "frozen" (heartbeats only, the gap keeps growing) is
        distinguishable from "progressing" (pipeline lines keep landing
        between heartbeats). Diagnostic only — it never touches the
        pinned plain-status-label contract."""
        # V0.6.56 (Task 14 review BLOCKER fix): the liveness check goes
        # through the house _worker_is_running helper (shared.py) —
        # SimpleWorker is a BaseWorker=QObject whose API is is_running(),
        # NOT QThread.isRunning(); calling isRunning() here raised
        # AttributeError 15s into every run (the exact V0.6.55
        # construction-order BLOCKER class — invisible in a no-Qt sandbox).
        from ui_qt.views.service_dialogs.dialogs.shared import _worker_is_running

        worker = getattr(self, "_worker", None)
        if not _worker_is_running(worker):
            self._heartbeat_timer.stop()
            return
        from core.transcribe.pipeline_log import format_heartbeat_line

        self._append_live_log(
            format_heartbeat_line(
                run_started_ts=self._run_started_ts,
                last_update_ts=self._last_update_ts,
                now_ts=time.time(),
                last_msg=self._last_status_msg,
                engine=self._run_engine,
            )
        )

    def _on_failed(self, error_msg):
        self._heartbeat_timer.stop()
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("🎙️ Transcribe")
        self.status_label.setText(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "❌ Transcription Failed", error_msg)

    def _on_done(self, results):
        self._heartbeat_timer.stop()
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("🎙️ Transcribe")

        if isinstance(results, Exception):
            self.status_label.setText(f"❌ Error: {results}")
            return

        if results.get("error") and not results.get("raw_path"):
            self.status_label.setText(f"❌ {results['error']}")
            QMessageBox.critical(self, "❌ Failed", results["error"])
            return

        parts = []
        if results.get("raw_path"):
            parts.append(f"📄 Raw transcript: {Path(results['raw_path']).name}")
        if results.get("summary_path"):
            parts.append(f"📝 Summary: {Path(results['summary_path']).name}")
        if results.get("tutorial_path"):
            parts.append(f"📚 Tutorial guide: {Path(results['tutorial_path']).name}")
        if results.get("error"):
            parts.append(f"⚠️ Summary error: {results['error']}")

        summary_text = "\n".join(parts)
        self.status_label.setText(f"✅ Done!\n{summary_text}")

        QMessageBox.information(
            self,
            "✅ Transcription Complete",
            f"Transcription complete!\n\n{summary_text}\n\nOutput: {self.out_edit.text()}",
        )
