"""Transcribe Service dialog (V18.20.4.6, P5 / O-b2 split).

TranscribeServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import logging
from pathlib import Path

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from controller import Controller

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model (core.llm.model_taxonomy is a leaf module — stdlib-only, no cycle).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    _confirm_close_with_running_worker,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.78.0: Transcribe Service — video/audio → text + Obsidian summary
# ════════════════════════════════════════════════════════════════════════════


class TranscribeServiceDialog(QDialog):
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
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("🎙️ Transcribe Service")
        self.setMinimumSize(750, 650)
        self.setModal(True)
        self._worker = None

        from PySide6.QtWidgets import (
            QCheckBox as _QChB,
        )
        from PySide6.QtWidgets import (
            QComboBox as _QCB,
        )
        from PySide6.QtWidgets import (
            QGroupBox as _QGB,
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
            QProgressBar as _QPB2,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("🎙️ Transcribe Service")
        title.setObjectName("H2")
        lay.addWidget(title)

        desc = _QL(
            "Import a video or audio file → get a raw transcript + "
            "an Obsidian-friendly summarized version. Uses "
            "faster-whisper (GPU-accelerated) for transcription."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # ── Input file ────────────────────────────────────────────────
        input_group = _QGB("1. Input file (video or audio):")
        input_lay = _VL(input_group)
        file_row = _HL()
        self.file_edit = _QLE()
        self.file_edit.setPlaceholderText(
            "Pick a video (.mp4, .mkv, .avi) or audio (.mp3, .wav, .m4a) file…"
        )
        file_btn = _QPB("Browse…")
        file_btn.clicked.connect(self._pick_file)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(file_btn)
        input_lay.addLayout(file_row)
        lay.addWidget(input_group)

        # ── Options ───────────────────────────────────────────────────
        opt_group = _QGB("2. Options:")
        opt_lay = _VL(opt_group)

        # Whisper model
        model_row = _HL()
        model_row.addWidget(_QL("Whisper model:"))
        self.whisper_combo = _QCB()
        self.whisper_combo.addItem("small (recommended — good balance)", "small")
        self.whisper_combo.addItem("tiny (fastest — quick drafts)", "tiny")
        self.whisper_combo.addItem("base (fast — meetings)", "base")
        self.whisper_combo.addItem("medium (high accuracy)", "medium")
        self.whisper_combo.addItem("large-v3 (best accuracy — slow)", "large-v3")
        model_row.addWidget(self.whisper_combo)
        model_row.addStretch()
        opt_lay.addLayout(model_row)

        # LLM model for summary
        llm_row = _HL()
        llm_row.addWidget(_QL("Summary model (Ollama):"))
        self.llm_combo = _QCB()
        self.llm_combo.setEditable(True)
        # V18.20.4.12 (W-a10): was the NON-empero variant
        # "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest" — a KNOWN-BAD tag
        # that 404s on the rig; RIG_FALLBACK_MODEL is the working tag
        # (the combo refreshes from /api/tags when Ollama answers).
        self.llm_combo.addItem(RIG_FALLBACK_MODEL)
        llm_row.addWidget(self.llm_combo, 1)
        self.refresh_btn = _QPB("🔄")
        self.refresh_btn.setToolTip("Refresh Ollama models")
        self.refresh_btn.clicked.connect(self._refresh_models)
        llm_row.addWidget(self.refresh_btn)
        opt_lay.addLayout(llm_row)

        # Checkboxes
        self.cb_raw = _QChB("Save raw transcript (with timestamps)")
        self.cb_raw.setChecked(True)
        opt_lay.addWidget(self.cb_raw)

        self.cb_summary = _QChB("Generate Obsidian summary (requires Ollama)")
        self.cb_summary.setChecked(True)
        opt_lay.addWidget(self.cb_summary)

        lay.addWidget(opt_group)

        # ── Output ────────────────────────────────────────────────────
        out_group = _QGB("3. Output:")
        out_lay = _VL(out_group)
        out_row = _HL()
        out_row.addWidget(_QL("Save to:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose output folder…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        out_lay.addLayout(out_row)
        lay.addWidget(out_group)

        # ── Process button ────────────────────────────────────────────
        self.process_btn = _QPB("🎙️ Transcribe")
        self.process_btn.setObjectName("Primary")
        self.process_btn.clicked.connect(self._on_process)
        lay.addWidget(self.process_btn)

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
        lay.addLayout(live_row)

        # ── Progress ──────────────────────────────────────────────────
        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        # Refresh models
        self._refresh_models()

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the transcription
        # SimpleWorker runs — the "QThread: Destroyed while thread is still
        # running" abort class. Ask; on "close anyway" detach the worker
        # so the pipeline's result is discarded, not crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _refresh_models(self):
        """Fetch installed Ollama models.

        V0.6.8 (audit B5): routed through utils.network.list_ollama_models
        (safe_ollama_request → proxy-proof) — was a bare requests.get that
        broke on machines with HTTP_PROXY set.
        """
        from utils.network import list_ollama_models
        from utils.settings import Settings

        s = Settings()
        ollama_url = s.get("summarisation.ollama_url", "http://localhost:11434")
        try:
            # V0.6.8 (review-loop follow-up): timeout=5 preserves the
            # original bare-call latency budget (the helper default is 10).
            models = [m for m in list_ollama_models(ollama_url, timeout=5) if m]
            if models:
                current = self.llm_combo.currentText()
                self.llm_combo.clear()
                for m in models:
                    self.llm_combo.addItem(m)
                idx = self.llm_combo.findText(current)
                if idx >= 0:
                    self.llm_combo.setCurrentIndex(idx)
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)

    def _pick_file(self):
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
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _open_live_transcribe(self):
        """V13.31.0 (#7): Open the live microphone transcription dialog."""
        from ui_qt.views.service_dialogs.live_transcribe import LiveTranscribeDialog

        dlg = LiveTranscribeDialog(self)
        dlg.exec()

    def _on_process(self):
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
            "whisper_model": self.whisper_combo.currentData(),
            "llm_model": self.llm_combo.currentText().strip(),
            "save_raw": self.cb_raw.isChecked(),
            "save_summary": self.cb_summary.isChecked(),
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

        results = {"raw_path": None, "summary_path": None, "error": None}

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

        # Step 2: Transcribe
        self._emit_progress(10, f"🎙️ Loading whisper model '{whisper_model}'...")
        transcribe_result = transcribe_audio(
            audio_path,
            model_size=whisper_model,
            log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
            progress_callback=lambda pct, msg: self._emit_progress(pct, msg),
        )

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

        # Step 4: Summarize
        if save_summary:
            self._emit_progress(92, "📝 Summarizing with LLM...")
            summary = summarize_transcript(
                transcribe_result["text"],
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

        # Clean up temp audio
        if is_video and Path(audio_path).exists():
            try:
                Path(audio_path).unlink()
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

        self._emit_progress(100, "✅ Done!")
        return results

    def _emit_progress(self, pct: int, msg: str):
        worker = getattr(self, "_worker", None)
        if worker is not None:
            try:
                worker.progress.emit(pct, msg)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

    def _on_progress(self, pct: int, msg: str):
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
        if results.get("error"):
            parts.append(f"⚠️ Summary error: {results['error']}")

        summary_text = "\n".join(parts)
        self.status_label.setText(f"✅ Done!\n{summary_text}")

        QMessageBox.information(
            self,
            "✅ Transcription Complete",
            f"Transcription complete!\n\n{summary_text}\n\nOutput: {self.out_edit.text()}",
        )
