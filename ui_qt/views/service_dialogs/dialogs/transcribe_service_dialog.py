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

from controller import Controller

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model (core.llm.model_taxonomy is a leaf module — stdlib-only, no cycle).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from core.system.timeouts import UI_PROBE_TIMEOUT_S
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
)

logger = logging.getLogger(__name__)


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
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (its _on_progress override only
        # sets status text) — hide the dead toggle.
        self._log_toggle_btn.setVisible(False)

        # Refresh models (same position as the pre-B17 __init__ tail).
        self._refresh_models()
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
        self.engine_combo.addItem("faster-whisper (CTranslate2)", "faster_whisper")
        self.engine_combo.addItem("transcribe.cpp (Vulkan GPU)", "transcribe_cpp")
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        engine_row.addWidget(self.engine_combo)
        # V0.6.41: model browse button for transcribe.cpp (lets the owner
        # pick the GGUF model file — not just a hardcoded path).
        self.cpp_model_browse_btn = _QPB("📁 Model")
        self.cpp_model_browse_btn.setToolTip("Browse for the transcribe.cpp Whisper model file (.gguf/.bin)")
        self.cpp_model_browse_btn.clicked.connect(self._browse_cpp_model)
        self.cpp_model_browse_btn.setVisible(False)  # hidden until transcribe.cpp is selected
        engine_row.addWidget(self.cpp_model_browse_btn)
        engine_row.addStretch()
        layout.addLayout(engine_row)

        # V0.6.39 (W-s1): Whisper model — auto-detect + custom-path browse.
        # The combo shows the standard faster-whisper model sizes, PLUS any
        # locally-downloaded models found via auto-detection. A "Browse"
        # button lets the operator pinpoint a custom model folder on disk.
        model_row = _HL()
        model_row.addWidget(_QL("Whisper model:"))
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
        """V0.6.40 (W-t2): toggle the Whisper model row visibility based on
        the selected engine. transcribe.cpp uses its own model (set in
        the CONFIGURATION block or picked via the 📁 Model button), so
        the faster-whisper model combo + browse button are hidden when
        transcribe.cpp is selected."""
        engine = self.engine_combo.currentData()
        is_faster_whisper = engine == "faster_whisper"
        # Show/hide the whisper model row (combo + browse button).
        self.whisper_combo.setVisible(is_faster_whisper)
        self.whisper_browse_btn.setVisible(is_faster_whisper)
        # Show/hide the transcribe.cpp model browse button.
        self.cpp_model_browse_btn.setVisible(not is_faster_whisper)

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

    def _browse_cpp_model(self):
        """V0.6.41: Browse for the transcribe.cpp Whisper model file
        (.gguf or .bin). The selected path is saved to the app's settings
        (transcribe.transcribe_cpp_model) so the engine picks it up."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick transcribe.cpp Whisper model file",
            "",
            "Model files (*.gguf *.bin *.pt);;All files (*.*)",
        )
        if path:
            from utils.settings import Settings

            s = Settings()
            s.set("transcribe.transcribe_cpp_model", path)
            self.status_label.setText(
                f"✅ Model set: {Path(path).name} (saved to settings)"
            )

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

        # Step 2: Transcribe (V0.6.40: dispatch to selected engine)
        engine = options.get("engine", "faster_whisper")
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

        # V0.6.53: log how much text was extracted
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

        # Step 4: Summarize (core concepts + key takeaways)
        if save_summary:
            self._emit_progress(92, "📝 Summarizing with LLM...")
            summary = summarize_transcript(
                _transcript_text,
                model=llm_model,
                ollama_url=ollama_url,
                log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                progress_callback=lambda pct, msg: self._emit_progress(pct, msg),
            )
            if not summary.startswith("Error:"):
                summary_path = out_folder / f"{file_stem}_summary.md"
                summary_path.write_text(summary, encoding="utf-8")
                results["summary_path"] = str(summary_path)
            else:
                results["error"] = summary  # summary error (non-fatal)

        # Step 5: Tutorial guide (educational / tips & tricks)
        if save_tutorial:
            self._emit_progress(95, "Generating tutorial guide with LLM...")
            tutorial = summarize_transcript(
                _transcript_text,
                model=llm_model,
                ollama_url=ollama_url,
                log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                progress_callback=lambda pct, msg: self._emit_progress(pct, msg),
                output_type="tutorial",
            )
            if not tutorial.startswith("Error:"):
                tutorial_path = out_folder / f"{file_stem}_tutorial.md"
                tutorial_path.write_text(tutorial, encoding="utf-8")
                results["tutorial_path"] = str(tutorial_path)
            else:
                if not results.get("error"):
                    results["error"] = tutorial

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
        if pct >= 0:
            self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_failed(self, error_msg):
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("🎙️ Transcribe")
        self.status_label.setText(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "❌ Transcription Failed", error_msg)

    def _on_done(self, results):
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
