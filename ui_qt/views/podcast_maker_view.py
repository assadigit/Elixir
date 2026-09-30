"""V11.37.0: Podcast Maker — content → script → audio with anti-hallucination.

New architecture:
  1. User pastes source material (bullet points, keypoints, text) or picks a file
  2. User selects: mode (lecture/conversational), tone, temperature, voices
  3. App generates a podcast script with DETERMINISTIC bullet coverage
  4. User reviews/edits the script
  5. App generates audio using TTS tool settings (NeuTTS/Kokoro for EN, Sherpa for FA)

Anti-hallucination system:
  - Constrained generation prompt (source_ref per line)
  - Deterministic coverage verification (every bullet MUST be covered)
  - Gap-fill reprompts (up to 2 retries)
  - Force-insert fallback (model CANNOT skip a bullet)
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller import Controller

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model (core.llm.model_taxonomy is a leaf module — stdlib-only, no cycle).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from core.podcast.audio_generator import generate_podcast_audio
from core.podcast.script_generator import (
    TEMPERATURE_PROFILES,
    TONE_PROFILES,
    ScriptResult,
    generate_podcast_script,
)

logger = logging.getLogger(__name__)


class PodcastMakerView(QWidget):
    """V11.37.0: Podcast Maker with deterministic anti-hallucination."""

    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._script_result: ScriptResult | None = None
        self._worker = None
        # V11.37.5: progress signal for thread-safe UI updates
        self._progress_signal = _ProgressSignal()
        self._progress_signal.progress.connect(self._on_progress_signal)
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setLayout(self._build_layout())
        scroll.setWidget(inner)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _build_layout(self) -> QVBoxLayout:
        root = QVBoxLayout()
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("🎙️ Podcast Maker")
        title.setObjectName("H1")
        root.addWidget(title)

        subtitle = QLabel(
            "Turn bullet points or keypoints into a podcast. "
            "Every bullet is guaranteed coverage — nothing is skipped."
        )
        subtitle.setObjectName("Caption")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ── Input section ──────────────────────────────────────────────
        input_group = QGroupBox("1. Source Material")
        input_layout = QVBoxLayout(input_group)

        input_btn_row = QHBoxLayout()
        self.file_btn = QPushButton("📁 Pick File (.md, .txt)")
        self.file_btn.clicked.connect(self._pick_file)
        input_btn_row.addWidget(self.file_btn)
        input_btn_row.addStretch()
        input_layout.addLayout(input_btn_row)

        self.file_label = QLabel("No file selected — paste content below")
        self.file_label.setObjectName("Caption")
        input_layout.addWidget(self.file_label)

        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText(
            "Paste your bullet points, keypoints, or source text here...\n\n"
            "Example:\n"
            "- Monk mode requires isolation for deep work\n"
            "- The cocoon stage lasts 90 days\n"
            "- Benedict's rule emphasizes community living\n"
            "- Vassa is the annual rains retreat"
        )
        self.input_text.setMinimumHeight(150)
        input_layout.addWidget(self.input_text)

        root.addWidget(input_group)

        # ── Settings section ───────────────────────────────────────────
        settings_group = QGroupBox("2. Podcast Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Mode + Tone row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("📚 Lecture (1 host)", "lecture")
        self.mode_combo.addItem("💬 Conversational (2 hosts)", "conversational")
        # V11.44.1: default to conversational
        self.mode_combo.setCurrentIndex(1)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        mode_row.addSpacing(16)

        mode_row.addWidget(QLabel("Tone:"))
        self.tone_combo = QComboBox()
        for key, profile in TONE_PROFILES.items():
            self.tone_combo.addItem(f"{key.title()} — {profile['desc']}", key)
        self.tone_combo.setCurrentIndex(2)  # casual
        mode_row.addWidget(self.tone_combo)
        mode_row.addStretch()
        settings_layout.addLayout(mode_row)

        # Temperature + Language row
        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Creativity:"))
        self.temp_combo = QComboBox()
        for label, val in TEMPERATURE_PROFILES.items():
            self.temp_combo.addItem(f"{label.title()} (temp={val})", val)
        self.temp_combo.setCurrentIndex(1)  # balanced (0.7)
        self.temp_combo.setToolTip(
            "Temperature controls creativity.\n"
            "Conservative (0.6) = safe, predictable\n"
            "Balanced (0.7) = Qwythos recommended\n"
            "Creative (0.8) = Qwythos max\n"
            "Very Creative (0.9) = above Qwythos range"
        )
        temp_row.addWidget(self.temp_combo)
        temp_row.addSpacing(16)

        temp_row.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Farsi (فارسی)", "fa")
        temp_row.addWidget(self.lang_combo)
        temp_row.addStretch()
        settings_layout.addLayout(temp_row)

        # Model row
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        # V11.37.2: use default model from settings
        # V18.20.4.12 (W-a10): was the NON-empero variant
        # "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest" — a KNOWN-BAD tag
        # that 404s on the rig (utils/settings.py:989-990 documents the
        # mismatch); RIG_FALLBACK_MODEL is the working tag. Only reached
        # when settings are empty AND Ollama is unreachable (combo
        # refreshes from /api/tags otherwise).
        default_model = self.controller.get_setting("summarisation.model", RIG_FALLBACK_MODEL)
        self.model_combo.addItem(default_model)
        model_row.addWidget(self.model_combo, 1)
        self.refresh_models_btn = QPushButton("🔄 Refresh")
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self.refresh_models_btn)
        settings_layout.addLayout(model_row)

        # Voices row
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Host A voice:"))
        self.host_a_combo = QComboBox()
        self.host_a_combo.setEditable(True)
        # V11.44.1: Kokoro default + VibeVoice optional
        from core.tts.vibevoice_engine import VIBEVOICE_ENGLISH_VOICES
        from core.tts.voices import KOKORO_VOICES

        for entry in KOKORO_VOICES[:6]:
            voice_id, _lang, gender, desc = entry
            self.host_a_combo.addItem(f"Kokoro — {voice_id} ({gender})", voice_id)
        for voice_id, display_name, gender, _native in VIBEVOICE_ENGLISH_VOICES:
            self.host_a_combo.addItem(
                f"VibeVoice — {display_name} ({gender})", f"vibevoice:{voice_id}"
            )
        self.host_a_combo.setCurrentIndex(0)  # Default: af_heart (Kokoro)
        voice_row.addWidget(self.host_a_combo)
        voice_row.addSpacing(16)

        # V11.44.1: Host B label + combo (hidden in lecture mode)
        self.host_b_label = QLabel("Host B voice:")
        voice_row.addWidget(self.host_b_label)
        self.host_b_combo = QComboBox()
        self.host_b_combo.setEditable(True)
        for entry in KOKORO_VOICES[:6]:
            voice_id, _lang, gender, desc = entry
            self.host_b_combo.addItem(f"Kokoro — {voice_id} ({gender})", voice_id)
        for voice_id, display_name, gender, _native in VIBEVOICE_ENGLISH_VOICES:
            self.host_b_combo.addItem(
                f"VibeVoice — {display_name} ({gender})", f"vibevoice:{voice_id}"
            )
        self.host_b_combo.setCurrentIndex(3)  # Default: am_michael (different from A)
        voice_row.addWidget(self.host_b_combo)
        voice_row.addStretch()
        settings_layout.addLayout(voice_row)

        # V11.44.1: same-voice warning label
        self.voice_warning_label = QLabel("")
        self.voice_warning_label.setStyleSheet("color: #e67e22; font-size: 12px;")
        self.voice_warning_label.setVisible(False)
        settings_layout.addWidget(self.voice_warning_label)

        # V11.44.1: connect voice change signals for warning
        self.host_a_combo.currentIndexChanged.connect(self._check_voice_warning)
        self.host_b_combo.currentIndexChanged.connect(self._check_voice_warning)

        root.addWidget(settings_group)

        # ── Generate script button ─────────────────────────────────────
        self.gen_script_btn = QPushButton("📝 Generate Podcast Script")
        self.gen_script_btn.setObjectName("Primary")
        self.gen_script_btn.clicked.connect(self._on_generate_script)
        root.addWidget(self.gen_script_btn)

        # ── Script preview ─────────────────────────────────────────────
        script_group = QGroupBox("3. Script Preview (editable)")
        script_layout = QVBoxLayout(script_group)

        self.coverage_label = QLabel("")
        self.coverage_label.setObjectName("Caption")
        script_layout.addWidget(self.coverage_label)

        self.script_preview = QPlainTextEdit()
        self.script_preview.setPlaceholderText(
            "Script will appear here after generation. You can edit it before generating audio."
        )
        self.script_preview.setMinimumHeight(200)
        script_layout.addWidget(self.script_preview)

        # V11.49.0: Import / Export script buttons
        script_btn_row = QHBoxLayout()
        script_btn_row.setSpacing(8)
        self.export_script_btn = QPushButton("📤 Export Script")
        self.export_script_btn.setObjectName("Compact")
        self.export_script_btn.setToolTip(
            "Save the current script as a .json file (preserves host/text/source_ref)."
        )
        self.export_script_btn.setEnabled(False)
        self.export_script_btn.clicked.connect(self._on_export_script)
        script_btn_row.addWidget(self.export_script_btn)

        self.import_script_btn = QPushButton("📥 Import Script")
        self.import_script_btn.setObjectName("Compact")
        self.import_script_btn.setToolTip(
            "Load a previously saved .json script file to re-generate audio from."
        )
        self.import_script_btn.clicked.connect(self._on_import_script)
        script_btn_row.addWidget(self.import_script_btn)

        script_btn_row.addStretch()
        script_layout.addLayout(script_btn_row)

        root.addWidget(script_group)

        # ── Generate audio button ──────────────────────────────────────
        self.gen_audio_btn = QPushButton("🎙️ Generate Podcast Audio")
        self.gen_audio_btn.setObjectName("Primary")
        self.gen_audio_btn.setEnabled(False)
        self.gen_audio_btn.clicked.connect(self._on_generate_audio)
        root.addWidget(self.gen_audio_btn)

        # ── Progress + status ──────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        # V11.51.0: Live log panel (toggleable) — shows real-time per-line
        # progress with timing + CUDA status during podcast generation.
        self._log_toggle_btn = QPushButton("📋 Show Live Log")
        self._log_toggle_btn.setObjectName("Compact")
        self._log_toggle_btn.setCheckable(True)
        self._log_toggle_btn.setChecked(False)
        self._log_toggle_btn.clicked.connect(self._toggle_live_log)
        root.addWidget(self._log_toggle_btn)

        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(200)
        self.live_log.setVisible(False)
        self.live_log.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; "
            "font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; "
            "border: 1px solid #3c3c3c; }"
        )
        root.addWidget(self.live_log)

        # ── Output path ────────────────────────────────────────────────
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Save to:"))
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Auto: Desktop/Podcast-YYYYMMDD-HHMMSS.wav")
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_btn)
        root.addLayout(out_row)

        root.addStretch()

        # V11.44.1: set initial mode state
        self._on_mode_changed()

        return root

    def _refresh_models(self) -> None:
        """V11.37.2: fetch installed models from Ollama /api/tags.

        V0.6.8 (audit B5): routed through utils.network.list_ollama_models /
        is_ollama_reachable (safe_ollama_request → proxy-proof) — was a bare
        requests.get that broke on machines with HTTP_PROXY set. The non-200
        "Ollama returned HTTP {status}" message folds into "Could not
        connect" (the helpers return list/bool, not status codes).
        """
        from utils.network import is_ollama_reachable, list_ollama_models
        from utils.settings import Settings

        s = Settings()
        ollama_url = s.get("summarisation.ollama_url", "http://localhost:11434")
        try:
            # V0.6.8 (review-loop follow-up): timeout=5 preserves the
            # original bare-call latency budget (the helper default is 10).
            models = [m for m in list_ollama_models(ollama_url, timeout=5) if m]
            if models:
                current = self.model_combo.currentText()
                self.model_combo.clear()
                for m in models:
                    self.model_combo.addItem(m)
                # Restore previous selection if still available
                idx = self.model_combo.findText(current)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                self.status_label.setText(f"✅ Found {len(models)} models")
            elif is_ollama_reachable(ollama_url):
                self.status_label.setText("⚠️ No models installed in Ollama")
            else:
                self.status_label.setText("⚠️ Could not connect to Ollama")
        except Exception as e:
            self.status_label.setText(f"⚠️ Could not connect to Ollama: {e}")

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick source file", "", "Text files (*.md *.txt);;All files (*.*)"
        )
        if path:
            self.file_label.setText(f"📄 {Path(path).name}")
            try:
                text = Path(path).read_text(encoding="utf-8")
                self.input_text.setPlainText(text)
            except Exception as e:
                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
                # user box (was str(e)-only — zero diagnostics).
                logger.warning("podcast source read failed", exc_info=True)
                QMessageBox.warning(self, "Error", f"Could not read file: {e}")

    def _pick_output(self) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default = f"Podcast-{ts}.wav"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save podcast audio",
            str(Path.home() / "Desktop" / default),
            "WAV audio (*.wav);;All files (*.*)",
        )
        if path:
            self.out_edit.setText(path)

    def _on_generate_script(self) -> None:
        source = self.input_text.toPlainText().strip()
        if not source:
            QMessageBox.warning(self, "No input", "Please paste source material first.")
            return

        mode = self.mode_combo.currentData()
        tone = self.tone_combo.currentData()
        temperature = self.temp_combo.currentData()
        language = self.lang_combo.currentData()
        model = self.model_combo.currentText().strip()

        self.gen_script_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText(
            "📝 Pre-processing source → extracting bullets → generating script..."
        )

        def _work():
            from utils.settings import Settings

            s = Settings()
            ollama_url = s.get("summarisation.ollama_url", "http://localhost:11434")
            return generate_podcast_script(
                source_text=source,
                mode=mode,
                tone=tone,
                temperature=temperature,
                language=language,
                ollama_url=ollama_url,
                model=model,
                log_callback=lambda msg, level="INFO": self._log(msg, level),
            )

        self._worker = _SimpleWorker(_work)
        self._worker.finished.connect(self._on_script_done)
        self._worker.start()

    def _on_script_done(self, result) -> None:
        self.progress_bar.setVisible(False)
        self.gen_script_btn.setEnabled(True)

        # V11.37.4: result might be an exception (from worker thread)
        if isinstance(result, Exception):
            self.status_label.setText(f"❌ Script generation failed: {result}")
            return
        if not hasattr(result, "error"):
            self.status_label.setText(f"❌ Unexpected result: {result}")
            return
        if result.error:
            self.status_label.setText(f"❌ {result.error}")
            return

        self._script_result = result
        self.script_preview.setPlainText(result.to_dialogue_text())
        # V11.49.0: enable export button once a script exists
        self.export_script_btn.setEnabled(True)

        # Show coverage info
        coverage_text = (
            f"✅ Coverage: {len(result.bullets_covered)}/{len(result.bullets_input)} "
            f"({result.coverage_pct:.0%}) | "
            f"Retries: {result.retries} | "
            f"Forced segments: {result.forced_segments}"
        )
        if result.bullets_missing:
            coverage_text += f" | ⚠️ Still missing: {[m + 1 for m in result.bullets_missing]}"
        self.coverage_label.setText(coverage_text)
        self.status_label.setText("✅ Script ready! Review/edit above, then generate audio.")
        self.gen_audio_btn.setEnabled(True)

    def _on_mode_changed(self) -> None:
        """V11.44.1: Show/hide Host B settings based on mode."""
        is_conversational = self.mode_combo.currentData() == "conversational"
        self.host_b_label.setVisible(is_conversational)
        self.host_b_combo.setVisible(is_conversational)
        if not is_conversational:
            self.voice_warning_label.setVisible(False)
        else:
            self._check_voice_warning()

    def _check_voice_warning(self) -> None:
        """V11.44.1: Warn if both hosts have the same voice."""
        if self.mode_combo.currentData() != "conversational":
            self.voice_warning_label.setVisible(False)
            return
        a = self.host_a_combo.currentData() or self.host_a_combo.currentText()
        b = self.host_b_combo.currentData() or self.host_b_combo.currentText()
        if a == b:
            self.voice_warning_label.setText(
                "⚠️ Warning: Host A and Host B have the same voice! "
                "For a natural conversation, pick different voices."
            )
            self.voice_warning_label.setVisible(True)
        else:
            self.voice_warning_label.setVisible(False)

    def _on_export_script(self) -> None:
        """V11.49.0: Export the current script as a .json file."""
        if not self._script_result or not self._script_result.lines:
            QMessageBox.warning(self, "No script", "Generate a script first.")
            return
        # If the user edited the preview, parse the edited text first.
        edited_text = self.script_preview.toPlainText().strip()
        if edited_text and edited_text != self._script_result.to_dialogue_text():
            self._parse_edited_script(edited_text)

        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_path = str(Path.home() / "Desktop" / f"Podcast-Script-{ts}.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Podcast Script", default_path, "JSON files (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self._script_result.to_json(), encoding="utf-8")
            self.status_label.setText(f"📤 Script exported to: {path}")
        except Exception as e:
            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
            # user box (was str(e)-only — zero diagnostics).
            logger.warning("podcast script export failed", exc_info=True)
            QMessageBox.critical(self, "Export failed", str(e))

    def _on_import_script(self) -> None:
        """V11.49.0: Import a .json script file and load it for audio generation."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Podcast Script", "", "JSON files (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
            # user box (was str(e)-only — zero diagnostics).
            logger.warning("podcast script read failed", exc_info=True)
            QMessageBox.critical(self, "Import failed", f"Could not read file:\n{e}")
            return
        try:
            from core.podcast.script_generator import ScriptResult

            result = ScriptResult.from_json(content)
        except Exception as e:
            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
            # user box (was str(e)-only — zero diagnostics).
            logger.warning("podcast script parse failed", exc_info=True)
            QMessageBox.critical(
                self,
                "Parse failed",
                f"Could not parse script JSON:\n{e}\n\n"
                "Expected format: a JSON array of objects with "
                "'host', 'text', 'source_ref', 'segment_type' fields, "
                "or a JSON object with a 'lines' array.",
            )
            return
        if not result.lines:
            QMessageBox.warning(
                self, "Empty script", "The file was parsed but contains no script lines."
            )
            return
        self._script_result = result
        self.script_preview.setPlainText(result.to_dialogue_text())
        self.export_script_btn.setEnabled(True)
        self.gen_audio_btn.setEnabled(True)
        self.coverage_label.setText(
            f"📥 Imported {len(result.lines)} lines from: {Path(path).name}"
        )
        self.status_label.setText("✅ Script imported! Review/edit above, then generate audio.")

    def _on_generate_audio(self) -> None:
        if not self._script_result:
            QMessageBox.warning(self, "No script", "Generate a script first.")
            return

        # If the user edited the script, update the lines
        edited_text = self.script_preview.toPlainText().strip()
        if edited_text and edited_text != self._script_result.to_dialogue_text():
            # Parse the edited text back into lines (simple format: [Host A] text)
            self._parse_edited_script(edited_text)

        host_a = self.host_a_combo.currentData() or self.host_a_combo.currentText().strip()
        host_b = self.host_b_combo.currentData() or self.host_b_combo.currentText().strip()

        # V11.51.0: Build a descriptive output path from the script title +
        # engine + speakers, format: Podcast-{title}-{engine}-{speakers}.wav
        out_path = self.out_edit.text().strip()
        if not out_path:
            import re as _re
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            # Get the LLM-generated title (or fallback)
            title = getattr(self._script_result, "title", "") or "Untitled"
            # Sanitize title for filename (remove invalid chars)
            safe_title = _re.sub(r"[^\w\s-]", "", title).strip()
            safe_title = _re.sub(r"[\s]+", "-", safe_title)[:50]
            # Determine engine name from the voice selection
            engine_name = "Kokoro"
            if host_a and str(host_a).startswith("vibevoice:"):
                engine_name = "VibeVoice"
            # Determine speakers
            mode = (
                self.mode_combo.currentData() if hasattr(self, "mode_combo") else "conversational"
            )
            if mode == "conversational":
                # Extract short speaker names from the combo text
                a_name = (
                    self.host_a_combo.currentText().split("—")[-1].strip().split("(")[0].strip()
                )
                b_name = (
                    self.host_b_combo.currentText().split("—")[-1].strip().split("(")[0].strip()
                )
                speakers = f"{a_name}+{b_name}"
            else:
                a_name = (
                    self.host_a_combo.currentText().split("—")[-1].strip().split("(")[0].strip()
                )
                speakers = a_name
            out_path = str(
                Path.home() / "Desktop" / f"Podcast-{safe_title}-{engine_name}-{speakers}-{ts}.wav"
            )
            self.out_edit.setText(out_path)

        self.gen_audio_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText("🎙️ Generating podcast audio...")

        def _work():
            from utils.settings import Settings

            s = Settings()
            return generate_podcast_audio(
                script=self._script_result,
                out_path=Path(out_path),
                host_a_voice=host_a,
                host_b_voice=host_b,
                settings=s,
                log_callback=lambda msg, level="INFO": self._log(msg, level),
                progress_callback=lambda pct, msg: self._progress(pct, msg),
            )

        self._worker = _SimpleWorker(_work)
        self._worker.finished.connect(self._on_audio_done)
        self._worker.start()

    def _on_audio_done(self, result) -> None:
        self.progress_bar.setVisible(False)
        self.gen_audio_btn.setEnabled(True)

        # V11.37.4: result might be an exception (from worker thread)
        if isinstance(result, Exception):
            self.status_label.setText(f"❌ Audio generation failed: {result}")
            QMessageBox.critical(
                self,
                "❌ Podcast Failed",
                f"Audio generation failed:\n\n{result}\n\nCheck the live log for details.",
            )
            return
        if result and isinstance(result, (str, Path)) and Path(result).exists():
            self.status_label.setText(f"✅ Podcast saved to: {result}")
            # V11.44.1: Generate a .txt report alongside the podcast
            self._generate_podcast_report(result)
            # V11.62.0: show a success modal with the saved folder + file
            self._show_podcast_success_modal(result)
        else:
            self.status_label.setText("❌ Audio generation failed — no output produced")
            QMessageBox.critical(
                self,
                "❌ Podcast Failed",
                "Audio generation produced no output.\n\nCheck the live log for details.",
            )

    def _show_podcast_success_modal(self, audio_path) -> None:
        """V11.62.0: Show a success modal with the saved folder + file."""
        import subprocess as _sp
        import sys as _sys
        from pathlib import Path as _P

        audio_p = _P(audio_path)
        folder = audio_p.parent
        # Get report path if it exists
        report_p = audio_p.with_suffix(".report.txt")
        report_line = f"\n📄 Report: {report_p.name}" if report_p.exists() else ""
        msg = QMessageBox(self)
        msg.setWindowTitle("✅ Podcast Complete")
        msg.setIcon(QMessageBox.Information)
        msg.setText(
            f"<h3>🎧 Podcast generated successfully!</h3>"
            f"<p><b>Audio file:</b> {audio_p.name}</p>"
            f"<p><b>Saved to:</b> {folder}</p>"
            f"<p><b>Size:</b> {audio_p.stat().st_size // 1024} KB</p>"
            f"{report_line}"
        )
        open_btn = msg.addButton("📂 Open Folder", QMessageBox.AcceptRole)
        msg.addButton("✓ Close", QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() is open_btn:
            # Open the folder in the OS file explorer with the file selected
            try:
                if _sys.platform == "win32":
                    _sp.Popen(["explorer", "/select,", str(audio_p)])
                elif _sys.platform == "darwin":
                    _sp.Popen(["open", "-R", str(audio_p)])
                else:
                    _sp.Popen(["xdg-open", str(folder)])
            except Exception:
                pass  # best-effort

    def _generate_podcast_report(self, audio_path) -> None:
        """V11.44.1: Generate a .txt report with podcast metadata."""
        import datetime as _dt
        from pathlib import Path as _P

        import soundfile as sf

        audio_p = _P(audio_path)
        report_path = audio_p.with_suffix(".report.txt")

        # Get audio info
        try:
            audio_data, sr = sf.read(str(audio_p))
            audio_duration = len(audio_data) / sr
            audio_size = audio_p.stat().st_size
        except Exception:
            audio_duration = 0
            audio_size = audio_p.stat().st_size if audio_p.exists() else 0

        # Get script info
        script_lines = len(self._script_result.lines) if self._script_result else 0
        script_chars = (
            sum(len(ln.text) for ln in self._script_result.lines) if self._script_result else 0
        )
        script_bullets = len(self._script_result.bullets_input) if self._script_result else 0
        coverage = f"{self._script_result.coverage_pct:.0%}" if self._script_result else "N/A"

        # Get voice info
        host_a = self.host_a_combo.currentText()
        mode = self.mode_combo.currentData()
        if mode == "conversational":
            host_b = self.host_b_combo.currentText()
        else:
            host_b = "N/A (lecture mode)"

        # Get settings
        tone = self.tone_combo.currentText()
        model = self.model_combo.currentText()
        language = self.lang_combo.currentText()
        temperature = self.temp_combo.currentData()

        report = f"""Podcast Generation Report
=========================
Generated: {_dt.datetime.now().isoformat()}
Audio file: {audio_p.name}

AUDIO INFO
----------
Duration: {audio_duration:.1f}s ({audio_duration / 60:.1f} min)
File size: {audio_size // 1024} KB
Sample rate: {sr if "sr" in dir() else "24000"} Hz

SCRIPT INFO
-----------
Total lines: {script_lines}
Total characters: {script_chars}
Bullet points covered: {script_bullets}
Coverage: {coverage}
Forced segments: {self._script_result.forced_segments if self._script_result else 0}
Retries: {self._script_result.retries if self._script_result else 0}

PODCAST SETTINGS
----------------
Mode: {mode}
Tone: {tone}
Language: {language}
Creativity (temperature): {temperature}
LLM Model: {model}

VOICES
------
Host A: {host_a}
Host B: {host_b}

SCRIPT CONTENT
--------------
{self.script_preview.toPlainText()[:5000] if self.script_preview else "N/A"}
"""
        try:
            report_path.write_text(report, encoding="utf-8")
            self.status_label.setText(
                f"✅ Podcast saved: {audio_p.name} | Report: {report_path.name}"
            )
        except Exception:
            pass

    def _parse_edited_script(self, text: str) -> None:
        """Parse edited dialogue text back into ScriptLine objects.

        V11.37.5: if a line looks like JSON, extract the text field
        instead of using the raw JSON as the spoken text.
        """
        import json
        import re

        from core.podcast.script_generator import ScriptLine

        lines = []
        for match in re.finditer(r"\[Host ([AB])\]\s*(.+?)(?=\[Host [AB]\]|$)", text, re.DOTALL):
            host = match.group(1)
            line_text = match.group(2).strip()
            if not line_text:
                continue
            # V11.37.5: if the text is JSON, extract the fields
            if line_text.startswith("{"):
                try:
                    obj = json.loads(line_text.rstrip(","))
                    if "host" in obj:
                        host = str(obj["host"]).strip().upper()[:1] or host
                    line_text = obj.get("text", "").strip()
                    if not line_text:
                        continue
                    lines.append(
                        ScriptLine(
                            host=host,
                            text=line_text,
                            source_ref=str(obj.get("source_ref", "edited")).lower(),
                            segment_type=obj.get("segment_type", "content"),
                        )
                    )
                    continue
                except json.JSONDecodeError:
                    pass  # treat as plain text
            lines.append(
                ScriptLine(host=host, text=line_text, source_ref="edited", segment_type="content")
            )
        if lines:
            self._script_result.lines = lines

    def _log(self, msg: str, level: str = "INFO") -> None:
        if hasattr(self.controller, "log"):
            self.controller.log(msg, level)
        # V11.51.0: also route to the live log panel
        self._progress_signal.progress.emit(-1, msg)

    def _progress(self, pct: int, msg: str) -> None:
        """Thread-safe progress update via signal."""
        # V11.37.5: use a signal instead of QMetaObject.invokeMethod
        # (Q_ARG was not imported and the approach was fragile).
        self._progress_signal.progress.emit(pct, msg)

    @Slot(int, str)
    def _on_progress_signal(self, pct: int, msg: str) -> None:
        """Receive progress update on the main thread (via signal)."""
        if pct >= 0:
            self.progress_bar.setValue(pct)
        self.status_label.setText(msg)
        # V11.51.0: append to the live log panel
        self._append_live_log(msg)

    def _toggle_live_log(self, checked: bool) -> None:
        """V11.51.0: Toggle the live log panel visibility."""
        self.live_log.setVisible(checked)
        self._log_toggle_btn.setText("📋 Hide Live Log" if checked else "📋 Show Live Log")

    def _append_live_log(self, msg: str) -> None:
        """V11.51.0: Append a message to the live log panel."""
        import datetime as _dt

        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self.live_log.appendPlainText(f"[{ts}] {msg}")
        sb = self.live_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def refresh_theme(self) -> None:
        pass  # handled by global theme manager


class _SignalBridge(QObject):
    """Thread-safe signal bridge for background workers."""

    finished = Signal(object)


class _ProgressSignal(QObject):
    """Thread-safe progress signal."""

    progress = Signal(int, str)


class _SimpleWorker(threading.Thread):
    """Simple background worker that calls a function and signals the result.

    Uses a _SignalBridge (QObject) for thread-safe signal emission.
    """

    def __init__(self, fn):
        super().__init__(daemon=True)
        self._fn = fn
        self.bridge = _SignalBridge()

    @property
    def finished(self):
        return self.bridge.finished

    def run(self):
        try:
            result = self._fn()
            self.bridge.finished.emit(result)
        except Exception as e:
            self.bridge.finished.emit(e)

    def start(self):
        super().start()
