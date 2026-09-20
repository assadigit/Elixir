"""V4.3.0: TTS settings page — a top-level head group in Settings.

Tab order (Voices first, per user request):
  1. **Voices** — Kokoro English voice selector, Piper Persian voice
     selector, and per-host (Host A / Host B) voice selectors.
  2. **Engines** — Piper binary path picker + live connectivity
     indicators (green/red circles) for both Kokoro and Piper.
  3. **Speed** — 0.5×–2.0× slider.
  4. **Preview** — "Test voice" button that plays a cached sample WAV
     in-app (via QSound) — no external media player. Samples are
     generated once and cached in ``config/voice_samples/``.

All settings persist under the ``tts.*`` namespace via the existing
``Controller`` settings layer.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.tts.voices import (
    KOKORO_DEFAULT_HOST_A,
    PIPER_FA_DEFAULT,
    PIPER_FA_VOICES,
    kokoro_voice_groups,
    piper_voice_label,
)
from ui_qt.components.file_picker_row import FilePickerRow
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings.widgets import make_form

logger = logging.getLogger(__name__)

# Where cached voice sample WAVs are stored (generated on first preview).
_SAMPLES_DIR = Path(__file__).resolve().parents[3] / "config" / "voice_samples"


# ── Section 1: Voices ─────────────────────────────────────────────────────


class TtsVoicesSection(QGroupBox):
    """Voice selectors for English, Persian, and the two podcast hosts.

    V4.5.0: Supports both Kokoro preset voices AND NeuTTS reference voices.
    The English voice selector adapts based on the selected EN engine:
    * If NeuTTS is selected → dropdown of reference voices (managed below)
    * If Kokoro is selected → dropdown of 16 preset voices

    Includes a "Manage reference voices" area for adding/removing NeuTTS
    cloned voices (wav + transcript pairs).
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Voices", parent)
        self.controller = controller
        f = make_form()

        # ── English engine selector ──────────────────────────────────────
        self.en_engine_combo = QComboBox()
        self.en_engine_combo.addItem("NeuTTS-Air (voice cloning, higher quality)", "neutts")
        self.en_engine_combo.addItem("Kokoro (preset voices, faster)", "kokoro")
        en_engine = controller.get_setting("tts.en_engine", "neutts")
        idx = self.en_engine_combo.findData(en_engine)
        if idx >= 0:
            self.en_engine_combo.setCurrentIndex(idx)
        self.en_engine_combo.currentIndexChanged.connect(self._on_en_engine_changed)
        f.addRow("English engine", self.en_engine_combo)

        # ── English voice (changes based on engine) ──────────────────────
        self.en_combo = QComboBox()
        self._populate_en_voices()
        f.addRow("English voice", self.en_combo)

        # ── Piper Persian voice ──────────────────────────────────────────
        self.fa_combo = QComboBox()
        for vid, _repo, _sub in PIPER_FA_VOICES:
            self.fa_combo.addItem(piper_voice_label(vid), vid)
        fa_current = controller.get_setting("tts.fa_voice", PIPER_FA_DEFAULT)
        self._select_combo_by_data(self.fa_combo, fa_current)
        f.addRow("Persian voice (Piper)", self.fa_combo)

        # ── Host A / Host B voices ───────────────────────────────────────
        self.host_a_combo = self._build_combined_voice_combo()
        self.host_b_combo = self._build_combined_voice_combo()
        host_a_current = controller.get_setting("tts.host_a_voice", "")
        host_b_current = controller.get_setting("tts.host_b_voice", "")
        if host_a_current:
            self._select_combo_by_data(self.host_a_combo, host_a_current)
        if host_b_current:
            self._select_combo_by_data(self.host_b_combo, host_b_current)
        f.addRow("Podcast Host A voice", self.host_a_combo)
        f.addRow("Podcast Host B voice", self.host_b_combo)

        # ── Reference voice manager (NeuTTS) ────────────────────────────
        f.addRow("", QLabel(""))  # spacer
        ref_label = QLabel("Reference Voices (NeuTTS voice cloning)")
        ref_label.setObjectName("SectionTitle")
        f.addRow("", ref_label)

        # List of reference voices + add/remove buttons
        self.ref_voices_list = QTextEdit()
        self.ref_voices_list.setReadOnly(True)
        self.ref_voices_list.setMaximumHeight(100)
        self._refresh_ref_voices_list()
        f.addRow("Available voices", self.ref_voices_list)

        # Add voice button
        self.add_voice_btn = QPushButton("＋  Add reference voice…")
        self.add_voice_btn.setCursor(Qt.PointingHandCursor)
        self.add_voice_btn.clicked.connect(self._on_add_voice)
        f.addRow("", self.add_voice_btn)

        # Remove voice button
        self.remove_voice_btn = QPushButton("🗑  Remove a reference voice…")
        self.remove_voice_btn.setCursor(Qt.PointingHandCursor)
        self.remove_voice_btn.clicked.connect(self._on_remove_voice)
        f.addRow("", self.remove_voice_btn)

        hint = QLabel(
            "NeuTTS clones voices from a 3-15s audio sample + its transcript. "
            "Add your own voice or any voice you have permission to clone. "
            "Host A / Host B can each be any voice (English or Persian). "
            "For a bilingual podcast, set one host to English, the other to Persian."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def _populate_en_voices(self) -> None:
        """Populate the English voice dropdown based on the selected engine."""
        self.en_combo.clear()
        en_engine = self.en_engine_combo.currentData() or "neutts"
        if en_engine == "kokoro":
            # Kokoro preset voices
            for _group_label, voices in kokoro_voice_groups():
                for vid, _lang, _gender, desc in voices:
                    self.en_combo.addItem(f"{vid} — {desc}", vid)
            current = self.controller.get_setting("tts.en_voice", KOKORO_DEFAULT_HOST_A)
        else:
            # NeuTTS reference voices
            from core.tts.voice_manager import VoiceManager

            vm = VoiceManager()
            voices = vm.list_voices()
            if not voices:
                self.en_combo.addItem("(no reference voices — add one below)", "")
            else:
                for v in voices:
                    label = v["name"]
                    if v["description"]:
                        label += f" — {v['description']}"
                    if not v["has_wav"]:
                        label += " (missing wav!)"
                    self.en_combo.addItem(label, v["name"])
            current = self.controller.get_setting("tts.en_voice", "dave")
        self._select_combo_by_data(self.en_combo, current)

    def _on_en_engine_changed(self) -> None:
        """When the EN engine changes, repopulate the voice dropdown."""
        self._populate_en_voices()

    def _refresh_ref_voices_list(self) -> None:
        """Refresh the read-only list of available reference voices."""
        from core.tts.voice_manager import VoiceManager

        vm = VoiceManager()
        voices = vm.list_voices()
        if not voices:
            self.ref_voices_list.setPlainText("(no reference voices yet)")
            return
        lines = []
        for v in voices:
            status = "✓" if v["has_wav"] else "✗"
            lines.append(f"  {status} {v['name']} — {v['description']}")
        self.ref_voices_list.setPlainText("\n".join(lines))

    def _on_add_voice(self) -> None:
        """Open a dialog to add a new reference voice."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QMessageBox

        from core.tts.voice_manager import VoiceManager

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Reference Voice")
        dlg.setMinimumSize(500, 300)
        lay = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g., my_voice (lowercase, no spaces)")
        lay.addRow("Voice name:", name_edit)

        wav_path_edit = QLineEdit()
        wav_path_edit.setPlaceholderText("Path to a 3-15s WAV file…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(
            lambda: wav_path_edit.setText(
                QFileDialog.getOpenFileName(dlg, "Select reference WAV", "", "WAV files (*.wav)")[0]
            )
        )
        wav_row = QHBoxLayout()
        wav_row.addWidget(wav_path_edit, 1)
        wav_row.addWidget(browse_btn)
        lay.addRow("Reference audio:", wav_row)

        transcript_edit = QLineEdit()
        transcript_edit.setPlaceholderText("Type EXACTLY what is said in the audio…")
        lay.addRow("Transcript:", transcript_edit)

        hint = QLabel(
            "The audio should be 3-15 seconds of a single person speaking "
            "clearly. The transcript must match the audio exactly for the "
            "cloning to work correctly."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        lay.addRow("", hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addRow(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            wav_path = wav_path_edit.text().strip()
            transcript = transcript_edit.text().strip()
            if not name or not wav_path or not transcript:
                QMessageBox.warning(
                    self, "Missing info", "Name, audio path, and transcript are all required."
                )
                return
            try:
                vm = VoiceManager()
                vm.add_voice(name, Path(wav_path), transcript)
                QMessageBox.information(
                    self, "Voice added", f"Reference voice '{name}' added successfully."
                )
                self._refresh_ref_voices_list()
                self._populate_en_voices()  # refresh the dropdown
            except Exception as e:
                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE
                # the user box (was str(e)-only — zero diagnostics).
                logger.warning("add reference voice failed", exc_info=True)
                QMessageBox.critical(self, "Failed to add voice", str(e))

    def _on_remove_voice(self) -> None:
        """Open a dialog to remove a reference voice."""
        from PySide6.QtWidgets import QMessageBox

        from core.tts.voice_manager import VoiceManager

        vm = VoiceManager()
        voices = vm.list_voices()
        if not voices:
            QMessageBox.information(self, "No voices", "No reference voices to remove.")
            return

        names = [v["name"] for v in voices]
        name, ok = QInputDialog.getItem(
            self, "Remove voice", "Select voice to remove:", names, 0, False
        )
        if ok and name:
            reply = QMessageBox.question(
                self,
                "Confirm removal",
                f"Remove reference voice '{name}'? This deletes the wav + txt files.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                vm.remove_voice(name)
                self._refresh_ref_voices_list()
                self._populate_en_voices()

    def _build_combined_voice_combo(self) -> QComboBox:
        """A combo listing ALL voices: NeuTTS reference + Kokoro + Piper."""
        combo = QComboBox()
        combo.addItem("(use per-language default)", "")

        # NeuTTS reference voices
        from core.tts.voice_manager import VoiceManager

        vm = VoiceManager()
        for v in vm.list_voices():
            combo.addItem(f"EN · {v['name']} — {v['description']}", v["name"])

        # Kokoro preset voices
        for _group_label, voices in kokoro_voice_groups():
            for vid, _lang, _gender, desc in voices:
                combo.addItem(f"EN · {vid} — {desc}", vid)

        # Piper Persian voices
        for vid, _repo, _sub in PIPER_FA_VOICES:
            combo.addItem(f"FA · {piper_voice_label(vid)}", vid)
        return combo

    @staticmethod
    def _select_combo_by_data(combo: QComboBox, data: str) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # If the saved voice isn't in the list (e.g., a NeuTTS reference
            # that was added after the combo was built), add it.
            if data:
                combo.insertItem(0, data, data)
                combo.setCurrentIndex(0)

    def save(self) -> None:
        c = self.controller
        c.update_setting("tts.en_engine", self.en_engine_combo.currentData() or "neutts")
        c.update_setting("tts.en_voice", self.en_combo.currentData() or "")
        c.update_setting("tts.fa_voice", self.fa_combo.currentData() or "")
        c.update_setting("tts.host_a_voice", self.host_a_combo.currentData() or "")
        c.update_setting("tts.host_b_voice", self.host_b_combo.currentData() or "")

    def reload(self) -> None:
        c = self.controller
        en_engine = c.get_setting("tts.en_engine", "neutts")
        idx = self.en_engine_combo.findData(en_engine)
        if idx >= 0:
            self.en_engine_combo.setCurrentIndex(idx)
        self._populate_en_voices()
        self._select_combo_by_data(self.fa_combo, c.get_setting("tts.fa_voice", PIPER_FA_DEFAULT))
        self._select_combo_by_data(self.host_a_combo, c.get_setting("tts.host_a_voice", ""))
        self._select_combo_by_data(self.host_b_combo, c.get_setting("tts.host_b_voice", ""))
        self._refresh_ref_voices_list()


# ── Section 2: Engines (with connectivity indicators) ─────────────────────


class TtsEnginesSection(QGroupBox):
    """Engine paths + live connectivity circles for all three engines.

    V4.5.0: Adds NeuTTS-Air (GGUF) config: GGUF model path + project path.
    Connectivity indicators now show three engines: NeuTTS, Kokoro, Piper.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Engines", parent)
        self.controller = controller
        f = make_form()

        # ── NeuTTS GGUF model path ───────────────────────────────────────
        neu_label = QLabel("NeuTTS-Air (English — primary)")
        neu_label.setObjectName("SectionTitle")
        f.addRow("", neu_label)

        self.neutts_gguf_picker = FilePickerRow(
            label="GGUF model",
            mode="file",
            placeholder=r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
            filter="GGUF model (*.gguf);;All files (*)",
        )
        self.neutts_gguf_picker.set_path(
            controller.get_setting(
                "tts.neutts_gguf_path",
                r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
            )
        )
        self.neutts_gguf_picker.path_changed.connect(self._recheck)
        f.addRow(self.neutts_gguf_picker)

        self.neutts_project_picker = FilePickerRow(
            label="NeuTTS project folder",
            mode="folder",
            placeholder=r"G:\Program Files\neutts-air",
        )
        self.neutts_project_picker.set_path(
            controller.get_setting(
                "tts.neutts_project_path",
                r"G:\Program Files\neutts-air",
            )
        )
        self.neutts_project_picker.path_changed.connect(self._recheck)
        f.addRow(self.neutts_project_picker)

        # ── V11.32.0: NeuTTS device selection ────────────────────────────
        # backbone = the expensive inference model. codec = audio decoder.
        # "cuda" = GPU (fast, ~10-15s/segment). "cpu" = slow (3-5 min).
        # "auto" = try CUDA, fall back to CPU.
        dev_row = QHBoxLayout()
        dev_row.setSpacing(8)

        dev_row.addWidget(QLabel("Backbone:"))
        self.neutts_backbone_combo = QComboBox()
        self.neutts_backbone_combo.addItem("GPU (cuda)", "cuda")
        self.neutts_backbone_combo.addItem("CPU (slow)", "cpu")
        self.neutts_backbone_combo.addItem("Auto", "auto")
        self.neutts_backbone_combo.setToolTip(
            "Where to run the main inference model.\n"
            "GPU = fast (~10-15s/segment).\n"
            "CPU = slow (~3-5 min/segment) but always works."
        )
        bb_pref = controller.get_setting("tts.neutts_backbone_device", "cuda")
        idx = self.neutts_backbone_combo.findData(bb_pref)
        self.neutts_backbone_combo.setCurrentIndex(idx if idx >= 0 else 0)
        dev_row.addWidget(self.neutts_backbone_combo)

        dev_row.addSpacing(12)
        dev_row.addWidget(QLabel("Codec:"))
        self.neutts_codec_combo = QComboBox()
        self.neutts_codec_combo.addItem("GPU (cuda)", "cuda")
        self.neutts_codec_combo.addItem("CPU", "cpu")
        self.neutts_codec_combo.addItem("Auto", "auto")
        self.neutts_codec_combo.setToolTip(
            "Where to run the audio codec.\nGPU is faster; CPU is the safe fallback."
        )
        cd_pref = controller.get_setting("tts.neutts_codec_device", "cuda")
        idx = self.neutts_codec_combo.findData(cd_pref)
        self.neutts_codec_combo.setCurrentIndex(idx if idx >= 0 else 0)
        dev_row.addWidget(self.neutts_codec_combo)

        dev_row.addStretch()
        dev_wrap = QWidget()
        dev_wrap.setLayout(dev_row)
        f.addRow("Devices", dev_wrap)

        self.neutts_subprocess_cb = QCheckBox(
            "Use subprocess mode (advanced — only if in-process conflicts)"
        )
        self.neutts_subprocess_cb.setChecked(
            bool(controller.get_setting("tts.neutts_use_subprocess", False))
        )
        self.neutts_subprocess_cb.setToolTip(
            "In-process mode (unchecked) is faster and the default.\n"
            "Check this ONLY if NeuTTS conflicts with the app's torch."
        )
        f.addRow("", self.neutts_subprocess_cb)

        # ── Piper binary path ─────────────────────────────────────────────
        f.addRow("", QLabel(""))  # spacer
        piper_label = QLabel("Piper (Persian)")
        piper_label.setObjectName("SectionTitle")
        f.addRow("", piper_label)

        self.piper_picker = FilePickerRow(
            label="Piper binary",
            mode="file",
            placeholder="C:\\piper_windows_amd64\\piper\\piper.exe",
            filter="Piper executable (piper.exe);;All files (*)",
        )
        self.piper_picker.set_path(
            controller.get_setting(
                "tts.piper_binary",
                r"C:\piper_windows_amd64\piper\piper.exe",
            )
        )
        self.piper_picker.path_changed.connect(self._recheck)
        f.addRow(self.piper_picker)

        # ── Connectivity indicators ──────────────────────────────────────
        f.addRow("", QLabel(""))  # spacer
        conn_row = QHBoxLayout()
        conn_row.setSpacing(16)

        # NeuTTS indicator
        self.neutts_dot = QLabel("●")
        self.neutts_dot.setFixedSize(20, 20)
        self.neutts_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.neutts_dot.setStyleSheet("font-size: 20px; color: #999;")
        conn_row.addWidget(self.neutts_dot)
        self.neutts_label = QLabel("NeuTTS-Air")
        conn_row.addWidget(self.neutts_label)

        conn_row.addSpacing(16)

        # Kokoro indicator
        self.kokoro_dot = QLabel("●")
        self.kokoro_dot.setFixedSize(20, 20)
        self.kokoro_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kokoro_dot.setStyleSheet("font-size: 20px; color: #999;")
        conn_row.addWidget(self.kokoro_dot)
        self.kokoro_label = QLabel("Kokoro")
        conn_row.addWidget(self.kokoro_label)

        conn_row.addSpacing(16)

        # Piper indicator
        self.piper_dot = QLabel("●")
        self.piper_dot.setFixedSize(20, 20)
        self.piper_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.piper_dot.setStyleSheet("font-size: 20px; color: #999;")
        conn_row.addWidget(self.piper_dot)
        self.piper_label = QLabel("Piper")
        conn_row.addWidget(self.piper_label)

        conn_row.addStretch()

        self.recheck_btn = QPushButton("Recheck")
        self.recheck_btn.setCursor(Qt.PointingHandCursor)
        self.recheck_btn.clicked.connect(self._recheck)
        conn_row.addWidget(self.recheck_btn)
        f.addRow("Connectivity", conn_row)

        kokoro_hint = QLabel(
            "NeuTTS-Air: set the GGUF model path + project folder (where the "
            "neutts package lives). Kokoro: Python package, no path needed "
            "(model downloads on first use). Piper: standalone binary for Persian."
        )
        kokoro_hint.setObjectName("Caption")
        kokoro_hint.setWordWrap(True)
        f.addRow("", kokoro_hint)

        self.setLayout(f)
        self._recheck()

    def _set_dot(self, label: QLabel, ok: bool) -> None:
        """Turn a connectivity dot green (ok) or red (not ok)."""
        color = "#22c55e" if ok else "#ef4444"  # green-500 / red-500
        label.setStyleSheet(f"font-size: 20px; color: {color};")

    def _recheck(self, *args) -> None:
        """Check all three engines and update the indicators.

        V18.20.4.9 (W-b8): the Kokoro connectivity check is an
        ``import kokoro`` — that can take SECONDS on first probe (it
        imports torch) and used to run on the UI thread from
        ``__init__``/``reload``/path-change handlers. It now runs on a
        SimpleWorker; the fast NeuTTS/Piper path checks stay synchronous
        (plain ``Path.exists``). The worker ref lives on
        ``self._kokoro_worker`` and the dot/label update happens on the
        main thread (``finished`` marshals there).
        """
        # NeuTTS: check GGUF + project folder exist
        gguf = self.neutts_gguf_picker.path()
        proj = self.neutts_project_picker.path()
        neutts_ok = (
            gguf is not None
            and gguf.exists()
            and proj is not None
            and proj.exists()
            and (Path(proj) / "neutts").is_dir()
        )
        self._set_dot(self.neutts_dot, neutts_ok)
        self.neutts_label.setText(f"NeuTTS-Air — {'connected' if neutts_ok else 'not found'}")

        # Kokoro: try to import (async — see docstring, W-b8)
        self._check_kokoro_async()

        # Piper: check binary exists
        piper_path = self.piper_picker.path()
        piper_ok = piper_path is not None and piper_path.exists()
        self._set_dot(self.piper_dot, piper_ok)
        self.piper_label.setText(
            f"Piper (Persian) — {'connected' if piper_ok else 'binary not found'}"
        )

    @staticmethod
    def _probe_kokoro() -> bool:
        """W-b8: the Kokoro import probe — widget-free, safe off-thread."""
        try:
            import importlib

            importlib.import_module("kokoro")
            return True
        except Exception:
            return False

    def _check_kokoro_async(self) -> None:
        """W-b8: run the Kokoro import probe off the UI thread."""
        worker = getattr(self, "_kokoro_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return  # a probe is already in flight — don't stack workers

        # While the probe runs the dot/label keep their previous state
        # (grey "Kokoro" before the first check — no red flash); the
        # update lands on the main thread when the probe finishes.
        w = SimpleWorker(self._probe_kokoro)
        self._kokoro_worker = w  # Python ref — can't be GC'd mid-run
        w.finished.connect(self._on_kokoro_probed)
        w.failed.connect(self._on_kokoro_probe_failed)
        w.start()

    def _on_kokoro_probed(self, kokoro_ok: bool) -> None:
        """W-b8: main-thread handler — update the Kokoro indicator."""
        self._set_dot(self.kokoro_dot, bool(kokoro_ok))
        self.kokoro_label.setText(f"Kokoro — {'connected' if kokoro_ok else 'not installed'}")

    def _on_kokoro_probe_failed(self, error: str) -> None:
        """W-b8/W-b18: fail-soft — the probe itself raised (log only; the
        label text is unchanged from the pre-check state)."""
        logger.warning("Kokoro connectivity probe failed: %s", error)
        self._set_dot(self.kokoro_dot, False)
        self.kokoro_label.setText("Kokoro — not installed")

    def save(self) -> None:
        c = self.controller
        gguf = self.neutts_gguf_picker.path()
        proj = self.neutts_project_picker.path()
        piper = self.piper_picker.path()
        c.update_setting("tts.neutts_gguf_path", str(gguf) if gguf else "")
        c.update_setting("tts.neutts_project_path", str(proj) if proj else "")
        c.update_setting("tts.piper_binary", str(piper) if piper else "")
        # V11.32.0: device prefs.
        c.update_setting(
            "tts.neutts_backbone_device", self.neutts_backbone_combo.currentData() or "cuda"
        )
        c.update_setting("tts.neutts_codec_device", self.neutts_codec_combo.currentData() or "cuda")
        c.update_setting("tts.neutts_use_subprocess", bool(self.neutts_subprocess_cb.isChecked()))

    def reload(self) -> None:
        c = self.controller
        self.neutts_gguf_picker.set_path(
            c.get_setting(
                "tts.neutts_gguf_path",
                r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
            )
        )
        self.neutts_project_picker.set_path(
            c.get_setting(
                "tts.neutts_project_path",
                r"G:\Program Files\neutts-air",
            )
        )
        self.piper_picker.set_path(
            c.get_setting(
                "tts.piper_binary",
                r"C:\piper_windows_amd64\piper\piper.exe",
            )
        )
        # V11.32.0: restore device selections.
        bb = c.get_setting("tts.neutts_backbone_device", "cuda")
        idx = self.neutts_backbone_combo.findData(bb)
        self.neutts_backbone_combo.setCurrentIndex(idx if idx >= 0 else 0)
        cd = c.get_setting("tts.neutts_codec_device", "cuda")
        idx = self.neutts_codec_combo.findData(cd)
        self.neutts_codec_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.neutts_subprocess_cb.setChecked(
            bool(c.get_setting("tts.neutts_use_subprocess", False))
        )
        self._recheck()


# ── Section 2b: Coqui XTTS v2 (V10.37.0) ─────────────────────────────────


class TtsCoquiSection(QGroupBox):
    """V10.37.0: Coqui XTTS v2 settings — better Persian TTS.

    Coqui XTTS v2 is a multilingual neural TTS with voice cloning.
    Supports Persian natively (unlike Piper's robotic voices).
    Requires: pip install TTS (+ torch for GPU).
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Coqui XTTS v2 (Better Persian TTS)", parent)
        self.controller = controller
        f = make_form()

        # Persian engine selector
        self.fa_engine_combo = QComboBox()
        self.fa_engine_combo.addItem("Piper (lightweight, robotic)", "piper")
        self.fa_engine_combo.addItem("Coqui XTTS v2 (neural, natural)", "coqui")
        _fa_idx = self.fa_engine_combo.findData(controller.get_setting("tts.fa_engine", "piper"))
        if _fa_idx >= 0:
            self.fa_engine_combo.setCurrentIndex(_fa_idx)
        f.addRow("Persian engine", self.fa_engine_combo)

        # Coqui model name
        self.coqui_model_edit = QLineEdit(
            controller.get_setting(
                "tts.coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2"
            )
        )
        f.addRow("Coqui model", self.coqui_model_edit)

        # Speaker name
        self.coqui_speaker_edit = QLineEdit(controller.get_setting("tts.coqui_speaker", "Ana"))
        f.addRow("Speaker name", self.coqui_speaker_edit)

        # Voice sample (for cloning)
        self.coqui_sample_picker = FilePickerRow(
            label="Voice sample (6s WAV for cloning, optional)",
            mode="file",
            filter="WAV files (*.wav);;All files (*.*)",
        )
        f.addRow(self.coqui_sample_picker)

        # Install hint
        hint = QLabel(
            "Install: pip install TTS && pip install torch torchaudio "
            "--index-url https://download.pytorch.org/whl/cu121\n"
            "Model downloads automatically on first use (~1.8 GB). "
            "Requires GPU for good speed (~2x realtime on RTX 3060)."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("tts.fa_engine", self.fa_engine_combo.currentData() or "piper")
        c.update_setting("tts.coqui_model", self.coqui_model_edit.text().strip())
        c.update_setting("tts.coqui_speaker", self.coqui_speaker_edit.text().strip())
        sample = self.coqui_sample_picker.path()
        c.update_setting("tts.coqui_voice_sample", str(sample) if sample else "")

    def reload(self) -> None:
        c = self.controller
        idx = self.fa_engine_combo.findData(c.get_setting("tts.fa_engine", "piper"))
        if idx >= 0:
            self.fa_engine_combo.setCurrentIndex(idx)
        self.coqui_model_edit.setText(
            c.get_setting("tts.coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2")
        )
        self.coqui_speaker_edit.setText(c.get_setting("tts.coqui_speaker", "Ana"))
        self.coqui_sample_picker.set_path(c.get_setting("tts.coqui_voice_sample", ""))


# ── Section 3: Speed ──────────────────────────────────────────────────────


class TtsSpeedSection(QGroupBox):
    """Synthesis speed slider (0.5×–2.0×), shared across both engines."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Speed", parent)
        self.controller = controller
        f = make_form()

        current = float(controller.get_setting("tts.speed", 1.0))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(50, 200)
        self.slider.setSingleStep(5)
        self.slider.setValue(int(current * 100))
        self.value_label = QLabel(f"{current:.2f}×")
        self.value_label.setMinimumWidth(48)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slider.valueChanged.connect(lambda v: self.value_label.setText(f"{v / 100:.2f}×"))
        row = QHBoxLayout()
        row.addWidget(self.slider)
        row.addWidget(self.value_label)
        f.addRow("Speed", row)

        hint = QLabel(
            "1.0× = natural speed. Higher = faster (Piper uses a shorter "
            "length scale; Kokoro uses a higher speed factor). Applies to "
            "both English and Persian synthesis."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def save(self) -> None:
        self.controller.update_setting("tts.speed", self.slider.value() / 100.0)

    def reload(self) -> None:
        current = float(self.controller.get_setting("tts.speed", 1.0))
        self.slider.setValue(int(current * 100))
        self.value_label.setText(f"{current:.2f}×")


# ── Section 3.5: Normalization (V4.4.0) ───────────────────────────────────


class TtsNormalizationSection(QGroupBox):
    """LLM-based text normalization before TTS.

    V4.4.0: Pre-processes text via an OpenAI-compatible endpoint before
    synthesis. For English: expands numbers, abbreviations, dates. For
    Persian: adds harakat (اعراب‌گذاری) + expands Persian numerals.

    Includes a "Test normalization" button that shows before/after for a
    sample sentence, so the user can verify harakat correctness before
    committing to a long conversion.
    """

    # Sample texts for the test button
    _SAMPLE_EN = "In 2024, Dr. Smith earned $50,000 from 3 projects at 3pm."
    _SAMPLE_FA = "در سال ۱۴۰۳، دکتر سمیت ۵۰۰۰۰ دلار از ۳ پروژه در ساعت ۳ عصر گرفت."

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Text Normalization (LLM pre-processing)", parent)
        self.controller = controller
        f = make_form()

        # Enable toggle
        self.enabled_cb = QCheckBox("Enable LLM text normalization before TTS")
        self.enabled_cb.setChecked(controller.get_setting("tts.normalize_enabled", True))
        self.enabled_cb.setToolTip(
            "Pre-processes each text segment via an LLM before synthesis.\n"
            "English: expands numbers, abbreviations, dates.\n"
            "Persian: adds harakat (اعراب‌گذاری) + expands numerals.\n"
            "Adds ~1 LLM call per segment (slower but better pronunciation)."
        )
        f.addRow(self.enabled_cb)

        # Endpoint
        self.endpoint_edit = QLineEdit(
            controller.get_setting("tts.normalize_endpoint", "http://localhost:11434/v1")
        )
        self.endpoint_edit.setPlaceholderText("http://localhost:11434/v1")
        f.addRow("Endpoint (OpenAI-compatible)", self.endpoint_edit)

        # API key (optional)
        self.apikey_edit = QLineEdit(controller.get_secret("tts.normalize_api_key", ""))
        self.apikey_edit.setEchoMode(QLineEdit.Password)
        self.apikey_edit.setPlaceholderText("(optional — leave blank for local Ollama)")
        f.addRow("API key", self.apikey_edit)
        # V0.16 (Phase 3 / 3.4): keychain storage indicator
        from core.system.secrets import storage_status_label

        f.addRow("", QLabel(storage_status_label()))

        # Model
        default_model = controller.get_setting(
            "tts.normalize_model",
            controller.get_setting("summarisation.model", "qwen2.5:3b"),
        )
        self.model_edit = QLineEdit(default_model)
        self.model_edit.setPlaceholderText("qwen2.5:3b (small/fast recommended)")
        f.addRow("Model", self.model_edit)

        # Context mode
        self.context_combo = QComboBox()
        self.context_combo.addItem("Per sentence (fast, isolated)", "sentence")
        self.context_combo.addItem("Per paragraph (balanced)", "paragraph")
        self.context_combo.addItem("Per segment (most context, slowest)", "segment")
        ctx = controller.get_setting("tts.normalize_context_mode", "sentence")
        idx = self.context_combo.findData(ctx)
        if idx >= 0:
            self.context_combo.setCurrentIndex(idx)
        f.addRow("Context mode", self.context_combo)

        # Custom prompts (collapsible — show a button to open a dialog)
        self.prompt_btn = QPushButton("Edit custom prompts (EN / FA)…")
        self.prompt_btn.setCursor(Qt.PointingHandCursor)
        self.prompt_btn.setToolTip(
            "Open a dialog to edit the normalization prompts.\n"
            "Defaults include harakat instructions for Persian."
        )
        self.prompt_btn.clicked.connect(self._edit_prompts)
        f.addRow("Prompts", self.prompt_btn)

        # Test button
        self.test_btn = QPushButton("🔍  Test normalization")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._on_test_clicked)
        f.addRow("", self.test_btn)

        hint = QLabel(
            "Pre-processes text via an LLM before TTS. For Persian, this adds "
            "harakat (فتحه/ضمه/کسره) to disambiguate pronunciation — critical "
            "for correct vowel sounds. Uses your local Ollama by default. "
            "Test before running a full conversion to verify harakat accuracy."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def _edit_prompts(self) -> None:
        """Open a dialog to edit the EN/FA normalization prompts."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTextEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Normalization Prompts")
        dlg.setMinimumSize(620, 480)
        lay = QVBoxLayout(dlg)

        tabs = QTabWidget()
        en_tab = QTextEdit()
        fa_tab = QTextEdit()
        en_tab.setPlainText(self._load_prompt("en"))
        fa_tab.setPlainText(self._load_prompt("fa"))
        tabs.addTab(en_tab, "English")
        tabs.addTab(fa_tab, "فارسی (Persian)")
        lay.addWidget(tabs)

        # Reset to default button
        reset_btn = QPushButton("Reset to defaults")
        reset_btn.clicked.connect(
            lambda: (
                en_tab.setPlainText(self._default_prompt("en")),
                fa_tab.setPlainText(self._default_prompt("fa")),
            )
        )
        lay.addWidget(reset_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.controller.update_setting("tts.normalize_prompt_en", en_tab.toPlainText())
            self.controller.update_setting("tts.normalize_prompt_fa", fa_tab.toPlainText())

    def _load_prompt(self, lang: str) -> str:
        """Load the saved prompt, or the default if none saved."""
        key = f"tts.normalize_prompt_{lang}"
        saved = self.controller.get_setting(key, "")
        if saved:
            return saved
        return self._default_prompt(lang)

    @staticmethod
    def _default_prompt(lang: str) -> str:
        from core.tts.normalizer import _DEFAULT_PROMPT_EN, _DEFAULT_PROMPT_FA

        return _DEFAULT_PROMPT_FA if lang == "fa" else _DEFAULT_PROMPT_EN

    def _on_test_clicked(self) -> None:
        """Run normalization on a sample and show before/after.

        V18.20.4.9 (W-b8): the two ``norm.normalize`` LLM calls used to run
        synchronously ON the UI thread (the "⏳  Normalizing…" text never
        even repainted). They now run on a SimpleWorker — the worker
        settings are snapshotted here on the MAIN thread (the worker body
        reads no widgets), results + the before/after dialog are built on
        the main thread (``finished`` marshals there), and the button is
        re-enabled in BOTH outcome handlers (W-b18 class).
        """
        # Snapshot on the MAIN thread — the worker body is widget-free.
        endpoint = self.endpoint_edit.text() or "http://localhost:11434/v1"
        api_key = self.apikey_edit.text()
        model = self.model_edit.text() or "qwen2.5:3b"
        prompt_en = self._load_prompt("en") or None
        prompt_fa = self._load_prompt("fa") or None
        context_mode = self.context_combo.currentData() or "sentence"
        samples = (
            ("English", self._SAMPLE_EN, "en"),
            ("فارسی", self._SAMPLE_FA, "fa"),
        )

        worker = getattr(self, "_test_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return  # a test run is already in flight — don't stack workers

        self.test_btn.setEnabled(False)
        self.test_btn.setText("⏳  Normalizing…")

        def _work():
            # V18.20.4.9 (W-b17): the per-sample traceback reaches the log
            # BEFORE the "(failed: …)" placeholder is shown to the user.
            from core.tts.normalizer import TextNormalizer

            # Build a normalizer from the snapshotted settings
            norm = TextNormalizer(
                endpoint=endpoint,
                api_key=api_key,
                model=model,
                custom_prompt_en=prompt_en,
                custom_prompt_fa=prompt_fa,
                context_mode=context_mode,
                log_callback=lambda m, lvl="INFO": None,
            )
            results = []
            for label, text, lang in samples:
                try:
                    normalized = norm.normalize(text, lang)
                except Exception as e:
                    logger.warning(
                        "normalization test failed for the %s sample", lang, exc_info=True
                    )
                    normalized = f"(failed: {e})"
                results.append((label, text, normalized))
            return results

        w = SimpleWorker(_work)
        self._test_worker = w  # Python ref — the QObject can't be GC'd mid-run
        w.finished.connect(self._on_test_finished)
        w.failed.connect(self._on_test_failed)
        w.start()

    def _on_test_finished(self, results) -> None:
        """W-b8: main-thread handler — re-enable + the identical dialog."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔍  Test normalization")

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        # Show results in a dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Normalization Test — Before / After")
        dlg.setMinimumSize(640, 440)
        dlay = QVBoxLayout(dlg)
        for label, before, after in results:
            dlay.addWidget(QLabel(f"<b>{label}</b>"))
            dlay.addWidget(QLabel(f"<b>Before:</b> {before}"))
            dlay.addWidget(QLabel(f"<b>After:</b> {after}"))
            dlay.addWidget(QLabel(""))  # spacer
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.close)
        buttons.accepted.connect(dlg.close)
        dlay.addWidget(buttons)
        dlg.exec()

    def _on_test_failed(self, error: str) -> None:
        """W-b8/W-b18: a raising worker must never leave the button stuck
        disabled — re-enable + fail-soft (log; no new user-visible text)."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔍  Test normalization")
        logger.warning("normalization test worker failed: %s", error)

    def save(self) -> None:
        c = self.controller
        c.update_setting("tts.normalize_enabled", self.enabled_cb.isChecked())
        c.update_setting("tts.normalize_endpoint", self.endpoint_edit.text().strip())
        # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
        c.set_secret("tts.normalize_api_key", self.apikey_edit.text().strip())
        c.update_setting("tts.normalize_model", self.model_edit.text().strip())
        c.update_setting(
            "tts.normalize_context_mode", self.context_combo.currentData() or "sentence"
        )

    def reload(self) -> None:
        c = self.controller
        self.enabled_cb.setChecked(c.get_setting("tts.normalize_enabled", True))
        self.endpoint_edit.setText(
            c.get_setting("tts.normalize_endpoint", "http://localhost:11434/v1")
        )
        self.apikey_edit.setText(c.get_secret("tts.normalize_api_key", ""))
        default_model = c.get_setting(
            "tts.normalize_model",
            c.get_setting("summarisation.model", "qwen2.5:3b"),
        )
        self.model_edit.setText(default_model)
        ctx = c.get_setting("tts.normalize_context_mode", "sentence")
        idx = self.context_combo.findData(ctx)
        if idx >= 0:
            self.context_combo.setCurrentIndex(idx)


# ── Section 4: Preview (in-app, cached samples) ───────────────────────────


class TtsPreviewSection(QGroupBox):
    """'Test voice' button — plays a cached sample WAV in-app via QMediaPlayer.

    V4.3.0: Instead of generating a new WAV each time and opening it in an
    external media player, samples are generated ONCE and cached in
    ``config/voice_samples/<voice_id>.wav``. Subsequent previews play
    instantly inside the app via QMediaPlayer (no external player, no
    file generation). A "Regenerate" button forces a fresh sample.

    The cache key is the voice ID, so each of the 16 Kokoro voices and 3
    Piper voices gets its own cached sample after first preview.
    """

    _SAMPLES = {
        "en": "Hello, this is a test of the selected voice. "
        "The quick brown fox jumps over the lazy dog.",
        "fa": "سلام، این یک تست برای صدای انتخاب‌شده است.",
    }

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Preview", parent)
        self.controller = controller
        self._player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None
        # V18.20.4.9 (W-b8): worker ref (GC hazard) + the (lang, voice) the
        # in-flight generation was started for (the failure boxes quote it).
        self._sample_worker: SimpleWorker | None = None
        self._pending_sample: tuple[str, str] | None = None
        f = make_form()

        # Language selector
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("فارسی (Persian)", "fa")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        f.addRow("Test language", self.lang_combo)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.test_btn = QPushButton("▶  Play sample")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(self.test_btn)

        self.regen_btn = QPushButton("Regenerate")
        self.regen_btn.setCursor(Qt.PointingHandCursor)
        self.regen_btn.setToolTip(
            "Generate a fresh sample with the current voice + speed. "
            "Useful after changing voices or speed."
        )
        self.regen_btn.clicked.connect(self._on_regenerate_clicked)
        btn_row.addWidget(self.regen_btn)

        btn_row.addStretch()
        f.addRow("", btn_row)

        # Cache status label
        self.cache_label = QLabel("")
        self.cache_label.setObjectName("Caption")
        f.addRow("", self.cache_label)

        hint = QLabel(
            "Plays a short sample in-app (no external media player). The "
            "first preview of each voice generates and caches a WAV in "
            "config/voice_samples/; subsequent previews are instant. Use "
            "Regenerate to refresh after changing voices or speed."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)
        self._on_lang_changed(0)

    def _on_lang_changed(self, _idx: int) -> None:
        lang = self.lang_combo.currentData()
        voice = self._current_voice_name(lang)
        self.test_btn.setText(f"▶  Play sample  ({voice})")
        self._update_cache_label()

    def _current_voice_name(self, lang: str) -> str:
        c = self.controller
        if lang == "fa":
            return c.get_setting("tts.fa_voice", PIPER_FA_DEFAULT)
        # English: depends on the selected engine
        en_engine = c.get_setting("tts.en_engine", "neutts")
        if en_engine == "kokoro":
            return c.get_setting("tts.en_voice", KOKORO_DEFAULT_HOST_A)
        return c.get_setting("tts.en_voice", "dave")

    def _sample_path(self, voice: str) -> Path:
        return _SAMPLES_DIR / f"{voice}.wav"

    def _update_cache_label(self) -> None:
        lang = self.lang_combo.currentData() or "en"
        voice = self._current_voice_name(lang)
        path = self._sample_path(voice)
        if path.exists():
            self.cache_label.setText(f"✓ Cached: {path.name} ({path.stat().st_size // 1024} KB)")
        else:
            self.cache_label.setText("○ Not cached yet (first play will generate it)")

    def _ensure_player(self) -> None:
        """Lazily create the QMediaPlayer + audio output."""
        if self._player is None:
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(1.0)
            # V18.20.4.9 (W-b19): connect ONCE at this one-time setup site.
            # The old per-click connect in _on_test_clicked added a
            # DUPLICATE mediaStatusChanged connection on every preview
            # (N clicks → N EndOfMedia resets; the P0 W-b3 duplicate-
            # delivery class in miniature).
            self._player.mediaStatusChanged.connect(self._on_playback_finished)

    def _play_in_app(self, path: Path) -> None:
        """Play a WAV file inside the app via QMediaPlayer (no external player)."""
        self._ensure_player()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def _engine_settings(self) -> dict:
        """V18.20.4.9 (W-b8): snapshot of the engine paths the sample
        generator reads — taken on the MAIN thread so the background
        worker body touches no widgets/live settings."""
        c = self.controller
        return {
            "en_engine": c.get_setting("tts.en_engine", "neutts"),
            "neutts_gguf": c.get_setting(
                "tts.neutts_gguf_path",
                r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
            ),
            "neutts_project": c.get_setting(
                "tts.neutts_project_path",
                r"G:\Program Files\neutts-air",
            ),
            "piper_binary": c.get_setting(
                "tts.piper_binary",
                r"C:\piper_windows_amd64\piper\piper.exe",
            ),
        }

    def _generate_sample(
        self, lang: str, voice: str, speed: float, cfg: dict | None = None
    ) -> tuple:
        """Generate a sample WAV and cache it. Returns (path_or_None, error_or_None).

        V18.20.4.9 (W-b8): ``cfg`` is the engine-settings snapshot
        (``_engine_settings``) taken on the MAIN thread; the background
        worker passes it so this body stays widget-free. Direct
        main-thread callers may omit it (snapshot taken here).
        """
        if cfg is None:
            cfg = self._engine_settings()
        text = self._SAMPLES[lang]
        out_path = self._sample_path(voice)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if lang == "en":
            en_engine = cfg["en_engine"]
            if en_engine == "neutts":
                # Use NeuTTS-Air
                from core.tts.neutts_engine import NeuTTSEngine

                gguf = Path(cfg["neutts_gguf"])
                proj = Path(cfg["neutts_project"])
                eng = NeuTTSEngine(
                    gguf_path=gguf,
                    neutts_project_path=proj,
                    log_callback=lambda m, lvl="INFO": None,
                )
            else:
                # Use Kokoro
                from core.tts.engine import KokoroEngine

                eng = KokoroEngine(log_callback=lambda m, lvl="INFO": None)
            ok = eng.synthesize(text, out_path, voice, speed)
            error = eng.last_error if not ok else None
        else:
            from core.tts.engine import PiperEngine

            piper_bin = Path(cfg["piper_binary"])
            eng = PiperEngine(
                piper_bin,
                piper_bin.parent / "voices",
                log_callback=lambda m, lvl="INFO": None,
            )
            ok = eng.synthesize(text, out_path, voice, speed)
            error = eng.last_error if not ok else None

        if ok and out_path.exists():
            return (out_path, None)
        return (None, error or "unknown error")

    def _on_test_clicked(self) -> None:
        """Play the cached sample; generate it first if not cached.

        V18.20.4.9 (W-b8): the first-play generation (engine load +
        synthesis — seconds for NeuTTS/Kokoro) used to run synchronously
        ON the UI thread, so the "⏳  Generating…" state never even
        repainted. It now runs on a SimpleWorker with the engine settings
        snapshotted on the MAIN thread (the worker body reads no widgets);
        the worker ref lives on ``self._sample_worker`` and the button is
        re-enabled in BOTH outcome handlers (W-b18 class).
        """
        lang = self.lang_combo.currentData() or "en"
        voice = self._current_voice_name(lang)
        speed = float(self.controller.get_setting("tts.speed", 1.0))
        path = self._sample_path(voice)

        if not path.exists():
            # Need to generate first
            worker = self._sample_worker
            try:
                in_flight = worker is not None and worker.is_running()
            except RuntimeError:
                in_flight = False  # worker already deleteLater'd itself
            if in_flight:
                return  # a generation is already in flight — don't stack workers

            self._pending_sample = (lang, voice)
            cfg = self._engine_settings()  # main-thread snapshot
            self.test_btn.setEnabled(False)
            self.test_btn.setText("⏳  Generating…")

            def _work():
                # V18.20.4.9 (W-b17): the traceback is logged at WARNING
                # BEFORE the "Preview failed" box reaches the user (the
                # old inline ``except`` reduced it to str(e) only).
                try:
                    return self._generate_sample(lang, voice, speed, cfg)
                except Exception:
                    logger.warning(
                        "TTS sample generation raised — traceback follows", exc_info=True
                    )
                    raise

            w = SimpleWorker(_work)
            self._sample_worker = w  # Python ref — can't be GC'd mid-run
            w.finished.connect(self._on_sample_generated)
            w.failed.connect(self._on_sample_failed)
            w.start()
            return

        if path and path.exists():
            self._play_in_app(path)
            self.test_btn.setText("▶  Playing…")
        else:
            QMessageBox.warning(self, "Preview failed", "Unexpected: no audio produced.")
            self._on_lang_changed(0)

    def _on_sample_generated(self, result) -> None:
        """W-b8: main-thread handler — play or show the identical error.

        Exceptions route here too: ``_on_sample_failed`` feeds this the
        ``(None, error)`` shape the old inline ``except`` produced, so the
        "Preview failed" box + button reset are byte-identical to the old
        behavior for BOTH the failed-generation and the raised paths.
        """
        self.test_btn.setEnabled(True)
        path, error = result
        lang, voice = self._pending_sample or (None, None)
        if voice is None:
            lang = self.lang_combo.currentData() or "en"
            voice = self._current_voice_name(lang)

        if not path:
            # Show the ACTUAL error, not a generic message
            QMessageBox.warning(
                self,
                "Preview failed",
                f"Could not generate audio with voice '{voice}'.\n\n"
                f"Error: {error}\n\n"
                f"Language: {lang}\n"
                f"Engine: {'Kokoro' if lang == 'en' else 'Piper'}\n\n"
                "For Kokoro: ensure it's installed (pip install kokoro) "
                "and the model can load.\n"
                "For Piper: ensure the binary path is correct (Engines tab).",
            )
            self._on_lang_changed(0)
            return

        if path and path.exists():
            self._play_in_app(path)
            self.test_btn.setText("▶  Playing…")
        else:
            QMessageBox.warning(self, "Preview failed", "Unexpected: no audio produced.")
            self._on_lang_changed(0)

    def _on_sample_failed(self, error: str) -> None:
        """W-b8/W-b18: a raising generator must never leave the button
        disabled — route through the identical failure display as a
        ``(None, error)`` result."""
        self._on_sample_generated((None, error))

    def _on_playback_finished(self, status) -> None:
        """Reset the play button when media finishes.
        (W-b19: connected once in _ensure_player — the one-time setup
        site — instead of on every preview click.)"""
        from PySide6.QtMultimedia import QMediaPlayer as QMP

        if status == QMP.MediaStatus.EndOfMedia:
            self._on_lang_changed(0)

    def _on_regenerate_clicked(self) -> None:
        """Force-generate a fresh sample with current voice + speed.

        V18.20.4.9 (W-b8): like the first-play path, the regeneration runs
        on a SimpleWorker (the engine load + synthesis blocked the UI
        thread before); re-entrancy guard + ref + re-enable in BOTH
        outcome handlers (W-b18 class).
        """
        lang = self.lang_combo.currentData() or "en"
        voice = self._current_voice_name(lang)
        speed = float(self.controller.get_setting("tts.speed", 1.0))

        worker = self._sample_worker
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return  # a generation is already in flight — don't stack workers

        self._pending_sample = (lang, voice)
        cfg = self._engine_settings()  # main-thread snapshot
        self.regen_btn.setEnabled(False)
        self.regen_btn.setText("⏳  Generating…")

        def _work():
            # V18.20.4.9 (W-b17): traceback at WARNING before the box.
            try:
                return self._generate_sample(lang, voice, speed, cfg)
            except Exception:
                logger.warning("TTS sample regeneration raised — traceback follows", exc_info=True)
                raise

        w = SimpleWorker(_work)
        self._sample_worker = w  # Python ref — can't be GC'd mid-run
        w.finished.connect(self._on_regenerate_finished)
        w.failed.connect(self._on_regenerate_failed)
        w.start()

    def _on_regenerate_finished(self, result) -> None:
        """W-b8: main-thread handler — identical cache/play/error behavior
        (a raised worker routes here as ``(None, error)``)."""
        self.regen_btn.setEnabled(True)
        self.regen_btn.setText("Regenerate")
        path, error = result
        lang, voice = self._pending_sample or (None, None)
        if voice is None:
            lang = self.lang_combo.currentData() or "en"
            voice = self._current_voice_name(lang)

        if path and path.exists():
            self._update_cache_label()
            self._play_in_app(path)
        else:
            QMessageBox.warning(
                self,
                "Regeneration failed",
                f"Could not generate audio with voice '{voice}'.\n\n"
                f"Error: {error}\n\n"
                "See the Engines tab to verify connectivity.",
            )

    def _on_regenerate_failed(self, error: str) -> None:
        """W-b8/W-b18: a raising generator must never leave the button
        disabled — route through the identical failure display."""
        self._on_regenerate_finished((None, error))

    def save(self) -> None:
        pass

    def reload(self) -> None:
        self._on_lang_changed(0)
