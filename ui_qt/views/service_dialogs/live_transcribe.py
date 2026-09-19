"""V13.31.0 (#7): Live Transcribe — real-time microphone transcription.

A sub-tool accessible from the Transcribe Service dialog. Uses the app's
existing Whisper (faster-whisper) engine to transcribe microphone input
in real-time.

Flow:
1. User clicks "🎤 Live Transcribe" in the Transcribe Service dialog
2. This dialog opens — user selects a Whisper model + language
3. User clicks "Start Recording" — the app warms up the model, then
   starts capturing audio from the default microphone
4. Audio is chunked every 3-5 seconds and sent to Whisper for transcription
5. Transcribed text appears in real-time in the text area
6. User clicks "Stop" — final transcript is saved as .md

The "warm up and run model first" directive means:
- The Whisper model is loaded BEFORE recording starts (so the first
  chunk doesn't have a 10s delay)
- A status label shows "Warming up model..." → "Ready — recording"
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _LiveTranscribeWorker(QThread):
    """Background thread for live microphone transcription.

    Captures audio from the default microphone in 3-second chunks,
    sends each chunk to faster-whisper for transcription, and emits
    the transcribed text via the ``chunk_transcribed`` signal.
    """

    chunk_transcribed = Signal(str)
    status_update = Signal(str, str)  # (message, level)
    error_occurred = Signal(str)

    def __init__(self, model_name: str = "small", language: str = "auto", parent=None):
        super().__init__(parent)
        self._model_name = model_name
        self._language = language
        self._stop_flag = threading.Event()
        self._whisper_model = None

    def run(self):
        """Main loop: warm up model → record → transcribe → emit."""
        try:
            # ── Phase 1: Warm up the model ────────────────────────────
            self.status_update.emit("Warming up Whisper model (this may take 10-20s)...", "INFO")

            try:
                from faster_whisper import WhisperModel
            except ImportError:
                self.error_occurred.emit(
                    "faster-whisper is not installed.\nInstall with: pip install faster-whisper"
                )
                return

            # Load model (GPU if available, else CPU)
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
            except ImportError:
                device = "cpu"
                compute_type = "int8"

            self.status_update.emit(f"Loading {self._model_name} model on {device}...", "INFO")
            self._whisper_model = WhisperModel(
                self._model_name, device=device, compute_type=compute_type
            )

            # ── Phase 2: Set up audio capture ─────────────────────────
            self.status_update.emit("Model ready. Setting up microphone...", "INFO")

            try:
                import numpy as np  # noqa: F401 — availability probe (sounddevice path needs numpy)
                import sounddevice as sd
            except ImportError:
                self.error_occurred.emit(
                    "sounddevice + numpy are required for live transcription.\n"
                    "Install with: pip install sounddevice numpy"
                )
                return

            # Audio config: 16kHz mono (Whisper requirement)
            sample_rate = 16000
            chunk_duration = 3.0  # seconds per chunk
            chunk_samples = int(sample_rate * chunk_duration)

            self.status_update.emit(
                f"🎤 Recording (model: {self._model_name}, device: {device})...", "INFO"
            )

            # ── Phase 3: Recording loop ───────────────────────────────
            while not self._stop_flag.is_set():
                # Record a chunk
                try:
                    audio = sd.rec(
                        chunk_samples, samplerate=sample_rate, channels=1, dtype="float32"
                    )
                    sd.wait()  # wait for recording to complete
                except Exception as e:
                    self.error_occurred.emit(f"Microphone error: {e}")
                    return

                if self._stop_flag.is_set():
                    break

                # Transcribe the chunk
                try:
                    audio_flat = audio.flatten()
                    lang = self._language if self._language != "auto" else None
                    segments, _ = self._whisper_model.transcribe(
                        audio_flat,
                        language=lang,
                        beam_size=1,  # fast for real-time
                    )
                    text = " ".join(seg.text for seg in segments).strip()
                    if text:
                        self.chunk_transcribed.emit(text + " ")
                except Exception as e:
                    # Don't crash on transcription errors — just log
                    self.status_update.emit(f"Transcription chunk error: {e}", "WARNING")

            self.status_update.emit("Recording stopped.", "INFO")

        except Exception as e:
            self.error_occurred.emit(f"Live transcribe error: {e}")

    def stop(self):
        """Signal the recording loop to stop."""
        self._stop_flag.set()


class LiveTranscribeDialog(QDialog):
    """V13.31.0 (#7): Live microphone transcription dialog.

    Opens from the Transcribe Service dialog as a sub-tool. Records audio
    from the default microphone and transcribes it in real-time using
    the app's Whisper engine.

    The model is warmed up BEFORE recording starts (per user directive:
    "warm up and run model first").
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("🎤 Live Transcribe")
        self.setMinimumSize(600, 450)
        self.setModal(True)
        self._worker: _LiveTranscribeWorker | None = None
        # V18.20.4.5 (T-b2): workers retired via Stop/close while still
        # winding down stay referenced here. Since this release the worker
        # is constructed WITHOUT a Qt parent (un-parented — see ``_start``),
        # so nothing but Python references keeps a running QThread alive:
        # dropping the last reference to a RUNNING thread aborts the whole
        # process ("QThread: Destroyed while thread is still running").
        self._retired_workers: list[_LiveTranscribeWorker] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # Title
        title = QLabel("🎤 Live Transcribe")
        title.setObjectName("H2")
        lay.addWidget(title)

        desc = QLabel(
            "Record audio from your microphone and transcribe it in real-time "
            "using the Whisper engine. The model is warmed up before recording "
            "starts for instant transcription."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Model selection
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Whisper model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("Tiny (fastest, ~1GB VRAM)", "tiny")
        self.model_combo.addItem("Base (fast, ~1GB VRAM)", "base")
        self.model_combo.addItem("Small (recommended, ~2GB VRAM)", "small")
        self.model_combo.addItem("Medium (slower, ~5GB VRAM)", "medium")
        self.model_combo.addItem("Large-v3 (best, ~10GB VRAM)", "large-v3")
        self.model_combo.setCurrentIndex(2)  # Small = recommended default
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        lay.addLayout(model_row)

        # Language selection
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto-detect", "auto")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Persian (Farsi)", "fa")
        self.lang_combo.addItem("Arabic", "ar")
        self.lang_combo.addItem("French", "fr")
        self.lang_combo.addItem("German", "de")
        self.lang_combo.addItem("Spanish", "es")
        self.lang_combo.addItem("Turkish", "tr")
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        lay.addLayout(lang_row)

        # Status label
        self.status_label = QLabel("Ready — click Start Recording to begin.")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(30)
        lay.addWidget(self.status_label)

        # Transcript text area
        self.transcript_text = QPlainTextEdit()
        self.transcript_text.setPlaceholderText("Transcribed text will appear here in real-time...")
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; }"
        )
        lay.addWidget(self.transcript_text, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = QPushButton("🎤 Start Recording")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.stop_btn)

        self.save_btn = QPushButton("💾 Save Transcript")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)
        lay.addLayout(btn_row)

    def _start(self):
        """Start recording — warms up the model first, then records."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self.transcript_text.clear()

        model_name = self.model_combo.currentData()
        language = self.lang_combo.currentData()

        # V18.20.4.5 (T-b2): a previous worker may still be winding down
        # after Stop (3s audio chunks + Whisper can outlast it) — retire it
        # before replacing the reference, or the old RUNNING thread would
        # lose its last reference and abort the process.
        self._stop_and_retire_worker()
        # V18.20.4.5 (T-b2): un-parented (was: parented to this dialog, so
        # closing the dialog destroyed a running QThread → hard abort).
        # self._worker below keeps it alive; see _stop_and_retire_worker
        # for the shutdown path.
        self._worker = _LiveTranscribeWorker(model_name, language, None)
        self._worker.chunk_transcribed.connect(self._on_chunk)
        self._worker.status_update.connect(self._on_status)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _stop_and_retire_worker(self, wait_ms: int = 0) -> None:
        """V18.20.4.5 (T-b2): stop the current worker and detach it safely.

        The worker is un-parented (see ``_start``), so closing this dialog
        no longer destroys a running QThread — but the flip side is that
        nothing but Python references keeps it alive. If it is still
        winding down (a 3s audio chunk plus Whisper transcription can
        outlast the best-effort wait), it is parked on
        ``_retired_workers`` and destroyed via ``deleteLater`` once it
        emits ``finished``, so a RUNNING QThread is never garbage-collected.
        """
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        worker.stop()
        if wait_ms:
            try:
                worker.wait(wait_ms)
            except Exception:
                pass  # best-effort
        if worker.isRunning():
            self._retired_workers.append(worker)
            worker.finished.connect(worker.deleteLater)

    def _stop(self):
        """Stop recording."""
        # V18.20.4.5 (T-b2): route through the retire helper — the old bare
        # ``self._worker = None`` could drop the last reference to a
        # still-winding-down un-parented QThread and abort the process
        # (that was harmless only while the worker was Qt-parented here).
        # Button behavior is unchanged.
        self._stop_and_retire_worker()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): closing while the recorder thread runs used to
        # abort with "QThread: Destroyed while thread is still running"
        # (worker was parented to this dialog, no guard). Stop it first.
        worker = self._worker
        if worker is not None and worker.isRunning():
            from PySide6.QtWidgets import QMessageBox

            ret = QMessageBox.question(
                self,
                "Recording in progress",
                "Live transcription is still running.\n\nStop recording and close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            try:
                worker.stop()
                worker.wait(2000)
            except Exception:
                pass  # best-effort
            # Still winding down after the 2s best-effort wait? Park it on
            # _retired_workers — dropping the last reference to a RUNNING
            # QThread is itself the abort this guard exists to prevent.
            self._worker = None
            if worker.isRunning():
                self._retired_workers.append(worker)
                worker.finished.connect(worker.deleteLater)
        super().closeEvent(event)

    def _on_chunk(self, text: str):
        """Append transcribed text to the text area."""
        cursor = self.transcript_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        # Auto-scroll to bottom
        self.transcript_text.setTextCursor(cursor)
        self.transcript_text.ensureCursorVisible()

    def _on_status(self, message: str, level: str):
        """Update the status label."""
        prefix = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "ℹ️")
        self.status_label.setText(f"{prefix} {message}")

    def _on_error(self, error: str):
        """Handle errors."""
        self.status_label.setText(f"❌ {error}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _save(self):
        """Save the transcript to a file."""
        from PySide6.QtWidgets import QFileDialog

        text = self.transcript_text.toPlainText().strip()
        if not text:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save transcript",
            "live_transcript.md",
            "Markdown (*.md);;Text (*.txt);;All files (*.*)",
        )
        if path:
            Path(path).write_text(text, encoding="utf-8")
            self.status_label.setText(f"✅ Saved to: {path}")
