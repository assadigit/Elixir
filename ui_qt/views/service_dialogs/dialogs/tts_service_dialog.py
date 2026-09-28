"""TTS Service dialog + CPU/GPU guardrails (V18.20.4.6, P5 / O-b2 split).

TtsServiceDialog and its V11.46.1 CPU-TTS confirm/warn helpers
(caches + _tts_cuda_available / _tts_torch_cuda_tag /
_is_cpu_tts_error / _show_cpu_tts_warning_modal /
_show_tts_gpu_error_modal) moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ; the dialog subclasses the shared
BaseServiceDialog. ui_qt.views.service_dialogs.base_dialog
re-exports everything (back-compat facade)."""

from __future__ import annotations

import logging
import re
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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    _confirm_close_with_running_worker,
    _show_success_modal,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.46.1: CPU-TTS guardrail — WARN + CONFIRM (not hard-block).
#
# The user's requirement: "if CPU tried to generate TTS, user must be
# warned by an error modal and confirm." V11.46.0 mis-implemented this as
# a hard BLOCK (QMessageBox.critical, no proceed option), which made TTS
# completely unusable when the main Python's torch lacks CUDA — even
# though VibeVoice runs in a separate subprocess with its own venv.
#
# V11.46.1 corrects this to a WARNING modal with Yes/No buttons:
#   • GPU available  → proceed silently
#   • VibeVoice voice → skip the check (its subprocess has its own venv)
#   • CPU + already confirmed this session → proceed (no nag)
#   • CPU + not yet confirmed → show warning, proceed only if user clicks Yes
# ════════════════════════════════════════════════════════════════════════════

# Cached result of torch.cuda.is_available() — checked once per session.
_tts_cuda_cache: bool | None = None

# Cached result of torch.version.cuda (None = CPU-only build).
_tts_cuda_tag_cache: str | None = None
_tts_cuda_tag_checked: bool = False

# Per-session flag: once the user confirms "continue on CPU", don't nag
# them again for every subsequent synthesis in the same session.
_cpu_confirmed_session: bool = False


def _tts_cuda_available() -> bool:
    """Return True if a CUDA GPU is available for TTS (cached).

    Imported lazily so the test suite (which has no torch) is unaffected.
    Any import/inspection error is treated as "no GPU" so the guardrail
    fires defensively.
    """
    global _tts_cuda_cache
    if _tts_cuda_cache is None:
        try:
            import torch

            _tts_cuda_cache = bool(torch.cuda.is_available())
        except Exception:
            _tts_cuda_cache = False
    return _tts_cuda_cache


def _tts_torch_cuda_tag() -> str | None:
    """Return torch.version.cuda (None = CPU-only build, '12.6' = CUDA build).

    This is the DEFINITIVE way to tell a CPU-only torch wheel from a CUDA
    wheel. On Windows `pip install torch` gives the CPU build by default;
    the CUDA build needs `--index-url https://download.pytorch.org/whl/cu126`.

    Cached + lazy so the test suite (no torch) is unaffected.
    """
    global _tts_cuda_tag_cache, _tts_cuda_tag_checked
    if not _tts_cuda_tag_checked:
        _tts_cuda_tag_checked = True
        try:
            import torch

            _tts_cuda_tag_cache = getattr(torch.version, "cuda", None)
        except Exception:
            _tts_cuda_tag_cache = None
    return _tts_cuda_tag_cache


def _is_cpu_tts_error(err_text: str) -> bool:
    """Heuristic: does this error text indicate a CPU/CUDA/GPU problem?

    Matches the RuntimeError messages raised by KokoroEngine and the
    VibeVoice subprocess when CUDA is unavailable, plus generic CUDA OOM.
    """
    if not err_text:
        return False
    t = err_text.lower()
    return any(
        kw in t
        for kw in (
            "cuda",
            "gpu",
            "cpu",
            "torch.cuda.is_available",
            "out of memory",
            "device",
            "no cuda",
        )
    )


def _show_cpu_tts_warning_modal(parent) -> bool:
    """V11.47.0: warning modal — detects the ROOT CAUSE and shows the fix.

    Returns True if the user clicks "Yes, continue on CPU", False if they
    cancel. Sets the per-session confirmation flag on Yes so subsequent
    syntheses in the same session don't nag.

    V11.47.0: now checks ``torch.version.cuda`` to distinguish:
      • None  → CPU-only torch build (the GPU code isn't in the wheel at
                all — no app fix possible; must reinstall torch)
      • '12.x' → CUDA build installed but cuda.is_available() is False
                (usually a driver mismatch)
    and shows the targeted message for each case.
    """
    global _cpu_confirmed_session
    cuda_tag = _tts_torch_cuda_tag()
    if cuda_tag is None:
        # ── CPU-only torch build — the real root cause ──────────────────
        title = "❌ CPU-Only torch Build — Reinstall Required"
        body = (
            "<h3>ROOT CAUSE: CPU-only PyTorch build</h3>"
            "<p><code>torch.version.cuda</code> is <b>None</b>, which means "
            "you installed the <b>CPU-only</b> torch wheel. The GPU/CUDA "
            "code is <b>not in the wheel at all</b> — no app change can "
            "make this torch use your GPU.</p>"
            "<p><b>FIX (run in your terminal, then restart the app):</b></p>"
            "<pre>pip uninstall -y torch torchvision torchaudio\n"
            "pip install torch --index-url "
            "https://download.pytorch.org/whl/cu126</pre>"
            "<p style='color:#888;font-size:small;'>(On Windows, "
            "<code>pip install torch</code> gives the CPU build by default "
            "— you must specify the CUDA index URL.)</p>"
            "<p><b>Continue on CPU anyway?</b> (VibeVoice will crash on CPU; "
            "only Kokoro will work, slowly.)</p>"
        )
    else:
        # ── CUDA build but not available — driver issue ────────────────
        title = "⚠️ No CUDA GPU — Continue on CPU?"
        body = (
            "<h3>TTS will run on CPU (very slow)</h3>"
            "<p>You have the CUDA build of torch (cuda="
            f"{cuda_tag}), but <code>torch.cuda.is_available()</code> "
            "returned <b>False</b>. This usually means the NVIDIA driver "
            "is missing or too old for this torch's CUDA version.</p>"
            "<p><b>Recommended fix:</b> update your NVIDIA driver from "
            "<a href='https://www.nvidia.com/Download/index.aspx'>"
            "nvidia.com/Download</a>, then restart the app.</p>"
            "<p><b>Continue on CPU anyway?</b> (VibeVoice will crash on CPU; "
            "only Kokoro will work, slowly.)</p>"
        )
    btn = QMessageBox.warning(
        parent,
        title,
        body,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if btn == QMessageBox.Yes:
        _cpu_confirmed_session = True
        return True
    return False


def _show_tts_gpu_error_modal(parent, err_text: str = "") -> None:
    """V11.46.1: critical modal for a REAL GPU/CUDA failure mid-generation.

    Used by the reactive path in _on_finished — i.e. the engine actually
    raised a CUDA error (OOM, driver crash, etc.) during synthesis, not
    just "no GPU at pre-flight". Requires OK to acknowledge.
    """
    detail = f"<p><b>Error:</b> {err_text[:300]}</p>" if err_text else ""
    QMessageBox.critical(
        parent,
        "🚫 TTS Failed — GPU/CUDA Error",
        "<h3>TTS failed due to a GPU/CUDA error</h3>"
        "<p>The engine raised an error during synthesis. This usually "
        "means a CUDA out-of-memory, a driver issue, or a torch/CUDA "
        "version mismatch.</p>"
        + detail
        + "<p><b>To fix:</b> install the CUDA build of PyTorch:</p>"
        "<pre>pip install torch --index-url "
        "https://download.pytorch.org/whl/cu126</pre>"
        "<p>Then restart the app.</p>",
        QMessageBox.Ok,
    )


class TtsServiceDialog(BaseServiceDialog):
    """Standalone TTS — text to natural speech audio."""

    # V11.35.0: Speaking style → (speed_multiplier, text_prefix_hint).
    # NeuTTS doesn't have native emotion params, so we approximate by:
    # 1. Adjusting the speed (enthusiastic = faster, dramatic = slower)
    # 2. Prepending an emotion cue in brackets (the LLM backbone picks up
    #    on these and adjusts prosody accordingly)
    # The text prefix is stripped from the final audio because NeuTTS
    # treats it as part of the input — but the prosody influence remains.
    _STYLE_PROFILES = {
        "natural": (1.0, ""),
        "inspiring": (0.95, "[inspiring tone] "),
        "enthusiastic": (1.10, "[enthusiastic] "),
        "calm": (0.90, "[calm, soothing] "),
        "authoritative": (0.95, "[authoritative] "),
        "friendly": (1.05, "[friendly, casual] "),
        "energetic": (1.15, "[energetic] "),
        "dramatic": (0.80, "[slow, dramatic] "),
    }

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(controller, "🎙️ TTS Service", parent, accept_files=True, accept_text=True)
        # V18.20.4.5 (T-b2): preview worker reference for the close guard.
        # (NOT a widget — the V11.41.6 warning below does not apply.)
        self._preview_worker: SimpleWorker | None = None
        # V11.41.6: DO NOT set these to None after super().__init__()!
        # super().__init__() calls _build_ui() → _build_options() which
        # creates these widgets. Setting them to None here OVERWRITES the
        # created widgets, making them inaccessible. This was the root
        # cause of VibeVoice never working — voice_combo was always None.

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard BOTH workers this dialog can have
        # running — the preview-clip worker (self._preview_worker) here,
        # and the full synthesis worker (self._worker) via the
        # BaseServiceDialog closeEvent that super() delegates to. Either
        # one closing mid-run is the "QThread: Destroyed while thread is
        # still running" abort class.
        if not _confirm_close_with_running_worker(self, self._preview_worker):
            event.ignore()
            return
        super().closeEvent(event)  # BaseServiceDialog guards self._worker

    def _build_options(self, layout: QVBoxLayout) -> None:
        # Language
        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)
        lang_row.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Farsi", "fa")
        self.lang_combo.addItem("Auto-detect", "auto")
        last = self._get_setting("language", "auto")
        idx = self.lang_combo.findData(last)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        # V11.41.2: connect AFTER setting initial index to prevent
        # spurious _on_lang_changed calls during setup
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(self.lang_combo)

        # V11.33.1: Format selector (.wav / .mp3)
        lang_row.addSpacing(16)
        lang_row.addWidget(QLabel("Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItem("WAV", ".wav")
        self.fmt_combo.addItem("MP3", ".mp3")
        last_fmt = self._get_setting("format", ".wav")
        idx = self.fmt_combo.findData(last_fmt)
        if idx >= 0:
            self.fmt_combo.setCurrentIndex(idx)
        self.fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        lang_row.addWidget(self.fmt_combo)

        lang_row.addStretch()
        layout.addLayout(lang_row)

        # Voice/engine — V11.33.0: dynamically populated based on language.
        voice_row = QHBoxLayout()
        voice_row.setSpacing(6)
        voice_row.addWidget(QLabel("Voice:"))
        self.voice_combo = QComboBox()
        self._populate_voices()  # V11.33.0: populate based on initial language
        # V11.42.0: update default filename when voice changes
        self.voice_combo.currentIndexChanged.connect(lambda: self._refresh_default_output())
        voice_row.addWidget(self.voice_combo)
        voice_row.addStretch()
        layout.addLayout(voice_row)

        # V11.35.0: Speaking Style selector — adjusts speed + adds emotion
        # hints to approximate different tones. NeuTTS doesn't have native
        # emotion params, so this uses speed + text prepending.
        style_row = QHBoxLayout()
        style_row.setSpacing(6)
        style_row.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItem("Natural (default)", "natural")
        self.style_combo.addItem(" Inspiring", "inspiring")
        self.style_combo.addItem(" Enthusiastic", "enthusiastic")
        self.style_combo.addItem(" Calm / soothing", "calm")
        self.style_combo.addItem(" Authoritative", "authoritative")
        self.style_combo.addItem(" Friendly / casual", "friendly")
        self.style_combo.addItem(" Energetic / upbeat", "energetic")
        self.style_combo.addItem(" Slow / dramatic", "dramatic")
        self.style_combo.setToolTip(
            "Speaking style adjusts speed and adds emotion cues.\n"
            "NeuTTS derives tone from the reference voice — for best\n"
            "results, pair the style with a matching reference voice."
        )
        last_style = self._get_setting("style", "natural")
        idx = self.style_combo.findData(last_style)
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        style_row.addWidget(self.style_combo)
        style_row.addStretch()
        layout.addLayout(style_row)

        # Preview button
        self.preview_btn = QPushButton("▶ Preview 5 seconds")
        self.preview_btn.setObjectName("Compact")
        self.preview_btn.clicked.connect(self._on_preview)
        layout.addWidget(self.preview_btn)

        # V11.48.0: Live GPU Status indicator — shows the ACTUAL
        # torch.cuda.is_available() measured INSIDE this app process
        # (not a separate CLI script). This is the definitive way to
        # tell whether the app process can see the GPU.
        gpu_row = QHBoxLayout()
        gpu_row.setSpacing(8)
        self.gpu_status_lbl = QLabel("GPU: checking…")
        self.gpu_status_lbl.setObjectName("Compact")
        self.gpu_status_lbl.setStyleSheet("padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        gpu_recheck_btn = QPushButton("🔄 Re-check")
        gpu_recheck_btn.setObjectName("Compact")
        gpu_recheck_btn.setFixedWidth(90)
        gpu_recheck_btn.clicked.connect(self._refresh_gpu_status)
        gpu_row.addWidget(self.gpu_status_lbl, 1)
        gpu_row.addWidget(gpu_recheck_btn)
        layout.addLayout(gpu_row)
        # Measure immediately (deferred so the dialog shows first).
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._refresh_gpu_status)

    def _on_format_changed(self) -> None:
        """V11.33.1: when the format changes, update the default output path."""
        self._refresh_default_output()

    def _pick_output(self) -> None:
        """V11.33.1: override to offer both WAV and MP3 in the file dialog."""
        default_name = self._default_output_name().rsplit(".", 1)[0]  # without ext
        # Pre-select the current format's extension.
        cur_ext = self._get_output_suffix()
        other_ext = ".mp3" if cur_ext == ".wav" else ".wav"
        filter_str = (
            f"Audio files (*{cur_ext} *{other_ext});;"
            f"WAV audio (*.wav);;"
            f"MP3 audio (*.mp3);;"
            f"All files (*.*)"
        )
        start_path = str(Path.home() / "Desktop" / f"{default_name}{cur_ext}")
        path, _ = QFileDialog.getSaveFileName(self, "Save audio output", start_path, filter_str)
        if path:
            # If the user typed a name without extension, add the selected one.
            p = Path(path)
            if p.suffix.lower() not in (".wav", ".mp3"):
                path = path + cur_ext
            self.out_path_edit.setText(path)
            # Sync the format combo to the chosen extension.
            if self.fmt_combo:
                ext = Path(path).suffix.lower()
                idx = self.fmt_combo.findData(ext)
                if idx >= 0:
                    self.fmt_combo.blockSignals(True)
                    self.fmt_combo.setCurrentIndex(idx)
                    self.fmt_combo.blockSignals(False)

    def _default_output_name(self) -> str:
        """V11.40.1: generate the default output filename.

        Format: ``[Engine][Speaker][Timestamp][WordCount].<ext>``

        Examples:
          Kokoro[af_heart][20260728-143022][45].wav
          VibeVoice[Carter][20260728-143022][45].wav
          Sherpa[nima][20260728-143022][30].wav
        """
        from datetime import datetime

        # Determine engine + speaker from the current selection
        voice_data = ""
        if self.voice_combo:
            voice_data = self.voice_combo.currentData() or ""
        lang = self.lang_combo.currentData() if self.lang_combo else "auto"

        # Determine engine name
        if voice_data and voice_data.startswith("omnivoice:"):
            engine = "OmniVoice"
            speaker = voice_data[len("omnivoice:") :]
        elif voice_data and voice_data.startswith("vibevoice:"):
            engine = "VibeVoice"
            speaker = voice_data[len("vibevoice:") :]
        elif lang == "fa":
            engine = "Kokoro"
            speaker = voice_data or "af_heart"
        else:
            # Default to Kokoro
            engine = "Kokoro"
            speaker = voice_data or "af_heart"

        # V11.40.1: count words in the input text
        input_text = self._get_input_text() if hasattr(self, "_get_input_text") else ""
        word_count = len(input_text.split()) if input_text else 0

        ext = ".wav"
        if self.fmt_combo:
            ext = self.fmt_combo.currentData() or ".wav"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Sanitize speaker name
        safe_speaker = "".join(c if c.isalnum() or c in "_-" else "" for c in speaker)
        return f"{engine}[{safe_speaker}][{ts}][{word_count}]{ext}"

    def _refresh_default_output(self) -> None:
        """V11.33.1: auto-fill the output path with a preset default name.

        V11.38.6: matches the new [Engine]-[Speaker]-[timestamp] format.
        Only fills if the field is empty OR contains a previous auto-generated
        name (so we don't overwrite a user's custom name).
        """
        if not hasattr(self, "out_path_edit") or self.out_path_edit is None:
            return
        current = self.out_path_edit.text().strip()
        # Fill if empty, or if it's a previous auto-generated name.
        # V11.40.1: match [Engine][Speaker][Timestamp][WordCount] format
        is_auto = (
            bool(
                re.match(
                    r"^[A-Za-z]+\[[A-Za-z0-9_]+\]\[\d{8}-\d{6}\]\[\d+\]\.(wav|mp3)$",
                    Path(current).name,
                    re.IGNORECASE,
                )
            )
            if current
            else True
        )
        if not is_auto:
            return  # user typed a custom name — don't overwrite
        # Use the parent directory of the current path (or Desktop as default).
        out_dir = str(Path(current).parent) if current else None
        if not out_dir or out_dir == ".":
            # Default to Desktop.
            out_dir = str(Path.home() / "Desktop")
        self.out_path_edit.setText(str(Path(out_dir) / self._default_output_name()))

    def showEvent(self, event) -> None:
        """V11.33.1: on dialog open, auto-fill the default output path."""
        super().showEvent(event) if hasattr(super(), "showEvent") else None
        self._refresh_default_output()

    def _on_lang_changed(self) -> None:
        """V11.33.0: repopulate the voice dropdown when the language changes.

        V11.41.2: preserve the current voice selection if it's still available
        in the new language. This prevents VibeVoice selection from being
        reset to Kokoro when the language changes.
        """
        # Remember the current selection so we can restore it if possible.
        prev = self.voice_combo.currentData() if self.voice_combo else ""
        self._populate_voices()
        if prev:
            idx = self.voice_combo.findData(prev)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)
            else:
                # Voice not available in new language — default to first real voice
                # (already done by _populate_voices)
                pass

    def _populate_voices(self) -> None:
        """V11.33.0: populate the voice combo based on the selected language.

        English → NeuTTS reference voices (from VoiceManager) + Kokoro voices.
        Farsi → Piper voices + Coqui speakers.
        Auto → a mix.
        """
        if not self.voice_combo:
            return
        self.voice_combo.clear()
        lang = self.lang_combo.currentData() if self.lang_combo else "auto"

        # V11.34.1: helper to add a non-selectable separator header.
        def _add_sep(label: str):
            self.voice_combo.addItem(label, "__separator__")
            idx = self.voice_combo.count() - 1
            # Make the separator non-selectable.
            model = self.voice_combo.model()
            if hasattr(model, "item"):
                item = model.item(idx)
                if item:
                    item.setEnabled(False)

        if lang in ("en", "auto"):
            # V11.43.1: Kokoro (fast) + VibeVoice (quality). Both kept.
            # ── Kokoro (Fast) ──
            from core.tts.voices import KOKORO_VOICES

            _add_sep("── Kokoro (Fast) ──")
            for entry in KOKORO_VOICES[:10]:
                voice_id, _lang, gender, desc = entry
                self.voice_combo.addItem(
                    f"Kokoro — {voice_id} ({gender}, {desc.split(',')[0]})", voice_id
                )

            # ── VibeVoice (Higher Quality, Slower) ──
            from core.tts.vibevoice_engine import VIBEVOICE_ENGLISH_VOICES

            _add_sep("── VibeVoice (Phone Quality, ~0.6x realtime = SLOW, 48kHz upsampled) ──")
            for voice_id, display_name, gender, _native in VIBEVOICE_ENGLISH_VOICES:
                self.voice_combo.addItem(
                    f"VibeVoice — {display_name} ({gender})", f"vibevoice:{voice_id}"
                )

        if lang in ("fa", "auto"):
            # V11.44.0: Kokoro for Farsi (no Farsi-specific engine, Kokoro handles it)
            _add_sep("── Kokoro Farsi ──")
            self.voice_combo.addItem("Kokoro — af_heart (Farsi)", "af_heart")
            self.voice_combo.addItem("Kokoro — am_michael (Farsi)", "am_michael")

        # Default to first real voice (skip separator headers).
        for i in range(self.voice_combo.count()):
            data = self.voice_combo.itemData(i)
            if data and data != "__separator__":  # real voice
                self.voice_combo.setCurrentIndex(i)
                break

    # ── V11.48.0: Live GPU status (measured INSIDE the app process) ───────
    def _refresh_gpu_status(self) -> None:
        """Measure torch.cuda.is_available() RIGHT NOW in this app process
        and update the GPU status label.

        V11.48.0: this is the definitive in-app probe. The standalone
        ``scripts/diagnose_tts_root_cause.py`` runs in a clean CLI process;
        this runs INSIDE the Qt app process (after PySide6 + QApplication
        are loaded), so it catches DLL-conflict issues that the CLI can't.
        """
        if not hasattr(self, "gpu_status_lbl") or self.gpu_status_lbl is None:
            return
        # Reset the cache so we re-measure fresh each time the user clicks
        # Re-check (otherwise the cache from the first call sticks).
        global _tts_cuda_cache, _tts_cuda_tag_cache, _tts_cuda_tag_checked
        _tts_cuda_cache = None
        _tts_cuda_tag_cache = None
        _tts_cuda_tag_checked = False

        try:
            import torch

            cuda_tag = getattr(torch.version, "cuda", None)
            avail = bool(torch.cuda.is_available())
            if avail:
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
                self.gpu_status_lbl.setText(
                    f"✅ GPU: {name} ({vram} MB) · torch.cuda=True · cu={cuda_tag}"
                )
                self.gpu_status_lbl.setStyleSheet(
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px;"
                    " background: #d4edda; color: #155724; border: 1px solid #c3e6cb;"
                )
            else:
                self.gpu_status_lbl.setText(
                    f"❌ GPU: NOT available · torch.cuda=False · cu={cuda_tag}"
                )
                self.gpu_status_lbl.setStyleSheet(
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px;"
                    " background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;"
                )
        except Exception as e:
            self.gpu_status_lbl.setText(f"❌ GPU: torch error — {e}")
            self.gpu_status_lbl.setStyleSheet(
                "padding: 4px 8px; border-radius: 4px; font-size: 11px;"
                " background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;"
            )

    # ── V11.46.1: CPU-TTS guardrail (warn + confirm, not hard-block) ──────
    def _guard_gpu_required(self) -> bool:
        """Pre-flight check: warn + confirm if no CUDA GPU is available.

        Returns True if it's safe to proceed, False to abort.

        V11.48.0: now also refreshes the GPU status label and logs the
        ACTUAL measured values to the status label, so the user can see
        exactly what the app process measured (not a cached/stale value).
        """
        # V11.48.0: refresh the live GPU indicator so it's always current.
        self._refresh_gpu_status()
        voice = self.voice_combo.currentData() if self.voice_combo else ""
        # VibeVoice runs via sys.executable subprocess — same torch as main.
        # (V11.46.1 incorrectly assumed a separate venv; corrected V11.47.0.)
        # We still skip the guard for VibeVoice because its subprocess does
        # its own CUDA check and will fall back to CPU with a warning.
        if voice and str(voice).startswith("vibevoice:"):
            return True
        cuda_avail = _tts_cuda_available()
        cuda_tag = _tts_torch_cuda_tag()
        if cuda_avail:
            return True
        global _cpu_confirmed_session
        if _cpu_confirmed_session:
            return True
        # Log the ACTUAL measured values so the user sees them.
        self.status_label.setText(
            f"⚠️ No CUDA in app process (torch.cuda=False, cu={cuda_tag}). See the warning modal."
        )
        if _show_cpu_tts_warning_modal(self):
            self.status_label.setText("⚠️ Proceeding on CPU (slow) — confirmed for this session.")
            return True
        self.status_label.setText("🚫 TTS cancelled — no CUDA GPU.")
        return False

    def _on_process(self) -> None:
        """V11.46.1: GPU guardrail before the normal TTS process flow.

        Overrides BaseServiceDialog._on_process to insert the CUDA
        warn+confirm pre-check. If the user cancels the warning, the
        worker is never started.
        """
        if not self._guard_gpu_required():
            return
        super()._on_process()

    def _on_preview(self) -> None:
        """Generate a 5-second preview clip for voice selection."""
        text = self._get_input_text()
        if not text.strip():
            QMessageBox.warning(self, "No text", "Paste some text first.")
            return
        # V11.46.1: GPU guardrail — preview also needs CUDA (or confirmation).
        if not self._guard_gpu_required():
            return
        # Take first ~100 chars for preview
        preview_text = text[:200]
        voice = self.voice_combo.currentData() if self.voice_combo else ""
        lang = self.lang_combo.currentData() if self.lang_combo else "auto"

        self.status_label.setText("Generating 5-second preview…")
        self.progress_bar.setVisible(True)
        self.preview_btn.setEnabled(False)

        def _do_preview():
            try:
                import tempfile
                from pathlib import Path as _P

                from utils.settings import Settings

                s = Settings()

                # Determine language
                if lang == "auto":
                    from core.tts.engine import detect_language

                    detected = detect_language(preview_text)
                else:
                    detected = lang

                # V11.40.0: simplified preview — Kokoro, VibeVoice, Sherpa only.
                synth_voice = voice or None
                if voice and voice.startswith("vibevoice:"):
                    voice_name = voice[len("vibevoice:") :]
                    vv_path = s.get("tts.vibevoice_model_path", "")
                    vv_voices = s.get("tts.vibevoice_voices_dir", "")
                    if vv_path:
                        from core.tts.engine_cache import get_vibevoice_engine

                        engine = get_vibevoice_engine(
                            model_path=vv_path,
                            voices_dir=vv_voices,
                            default_voice=voice_name,
                            log_callback=lambda msg, level="INFO": None,
                        )
                        synth_voice = voice_name
                    else:
                        from core.tts.engine import KokoroEngine

                        engine = KokoroEngine(log_callback=lambda msg, level="INFO": None)
                        # V0.6.0 (T1): the "vibevoice:…" id is not a Kokoro
                        # voice — drop it so Kokoro uses its default.
                        synth_voice = None
                elif detected == "fa":
                    # V11.44.0: Farsi preview: Kokoro
                    from core.tts.engine import KokoroEngine

                    engine = KokoroEngine(log_callback=lambda msg, level="INFO": None)
                else:
                    # English default: Kokoro (fast)
                    from core.tts.engine import KokoroEngine

                    engine = KokoroEngine(log_callback=lambda msg, level="INFO": None)

                tmp_path = _P(tempfile.mktemp(suffix=".wav"))
                # V11.31.7: single call, no splitting, no fallback.
                result = engine.synthesize(preview_text, tmp_path, synth_voice, 1.0)
                return str(result) if result else None
            except Exception as e:
                return f"Error: {e}"

        # V18.20.4.5 (T-b2): keep a reference on self (was a local
        # variable) so closeEvent can guard "close while preview is
        # generating". The worker itself is unchanged.
        self._preview_worker = SimpleWorker(_do_preview)
        self._preview_worker.finished.connect(lambda path: self._on_preview_done(path))
        self._preview_worker.failed.connect(lambda e: self._on_preview_done(f"Error: {e}"))
        self._preview_worker.start()

    def _on_preview_done(self, path) -> None:
        self.progress_bar.setVisible(False)
        self.preview_btn.setEnabled(True)
        if path and not str(path).startswith("Error"):
            self.status_label.setText(f"✅ Preview ready: {path}")
            # Play the audio
            try:
                from PySide6.QtCore import QUrl
                from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

                player = QMediaPlayer()
                audio = QAudioOutput()
                player.setAudioOutput(audio)
                player.setSource(QUrl.fromLocalFile(str(path)))
                player.play()
            except Exception:
                self.status_label.setText(f"✅ Preview saved: {path}")
        else:
            self.status_label.setText(f"❌ Preview failed: {path}")

    def _collect_options(self) -> dict:
        # V11.34.2: defensive None checks
        combo = self.voice_combo
        voice = combo.currentData() if combo else ""
        # V11.34.1: if a separator is selected (or voice is empty), find
        # the nearest real voice.
        if combo and (voice == "__separator__" or not voice):
            cur = combo.currentIndex()
            # Search forward.
            for i in range(cur + 1, combo.count()):
                data = combo.itemData(i)
                if data and data != "__separator__":
                    voice = data
                    combo.setCurrentIndex(i)
                    break
            else:
                # Search backward.
                for i in range(cur - 1, -1, -1):
                    data = combo.itemData(i)
                    if data and data != "__separator__":
                        voice = data
                        combo.setCurrentIndex(i)
                        break
        lang = self.lang_combo.currentData() if self.lang_combo else "auto"
        fmt = self.fmt_combo.currentData() if self.fmt_combo else ".wav"
        style = (
            self.style_combo.currentData()
            if hasattr(self, "style_combo") and self.style_combo
            else "natural"
        )
        self._save_setting("voice", voice)
        self._save_setting("language", lang)
        self._save_setting("format", fmt)
        self._save_setting("style", style)
        return {"voice": voice, "language": lang, "format": fmt, "style": style}

    def _get_output_suffix(self) -> str:
        # V11.33.1: return the selected format (.wav or .mp3).
        if self.fmt_combo:
            return self.fmt_combo.currentData() or ".wav"
        return ".wav"

    def _get_service_name(self) -> str:
        return "tts"

    def _save_result(self, result: Any, path: Path) -> str | None:
        """V11.33.1: save the temp WAV to the user's chosen output path.

        If the output is .mp3, converts the WAV→MP3 via pydub (requires
        ffmpeg). If ffmpeg isn't available, falls back to .wav and logs
        a warning. Returns the actual saved path.
        """
        if not (isinstance(result, str) and Path(result).exists()):
            return None

        path.parent.mkdir(parents=True, exist_ok=True)
        target_ext = path.suffix.lower()

        if target_ext == ".mp3":
            # V11.33.1: WAV → MP3 conversion via pydub.
            try:
                from pydub import AudioSegment

                audio = AudioSegment.from_wav(result)
                audio.export(str(path), format="mp3", bitrate="192k")
                return str(path)
            except Exception as e:
                # ffmpeg not installed or conversion failed — fall back to WAV.
                import logging

                logging.getLogger(__name__).warning(
                    "MP3 conversion failed (%s) — saving as WAV instead. "
                    "Install ffmpeg for MP3 support.",
                    e,
                )
                # Change the extension to .wav.
                wav_path = path.with_suffix(".wav")
                import shutil

                shutil.copy2(result, wav_path)
                # Update the out_path_edit so the UI shows the correct path.
                if hasattr(self, "out_path_edit"):
                    self.out_path_edit.setText(str(wav_path))
                return str(wav_path)
        else:
            # .wav — just copy.
            import shutil

            shutil.copy2(result, path)
            return str(path)

    def _on_finished(self, result: Any) -> None:
        """V11.33.0: override to NOT show the temp file path in the preview.

        V11.41.1: writes the proof file at the ACTUAL output path (not temp).
        V11.46.1: reactive GPU guardrail — if the engine actually FAILED
        with a CUDA/GPU error mid-generation (OOM, driver crash, etc.),
        surface it as a critical error modal requiring confirmation.
        """
        self._reset_ui()
        # Check for error strings returned by _process.
        if isinstance(result, str) and result.startswith("Error:"):
            # V11.46.1: real GPU/CUDA failures get the critical modal.
            if _is_cpu_tts_error(result):
                _show_tts_gpu_error_modal(self, result)
                self.status_label.setText(
                    "🚫 TTS failed — GPU/CUDA error. See the dialog for details."
                )
            else:
                self.status_label.setText(f"❌ {result}")
            self.again_btn.setVisible(True)
            return
        if isinstance(result, Exception):
            err_str = str(result)
            # V11.46.1: same reactive guardrail for raised exceptions.
            if _is_cpu_tts_error(err_str):
                _show_tts_gpu_error_modal(self, err_str)
                self.status_label.setText(
                    "🚫 TTS failed — GPU/CUDA error. See the dialog for details."
                )
            else:
                self.status_label.setText(f"❌ Script generation failed: {result}")
            return
        if not hasattr(result, "error"):
            # result might be a string path (from TTS _process)
            pass
        if result:
            out_path = Path(self.out_path_edit.text().strip())
            # _save_result copies the temp WAV to the user's chosen path.
            actual_path = self._save_result(result, out_path)
            if actual_path is None:
                actual_path = str(out_path)

            # V11.41.1: Write proof file at the ACTUAL output location
            engine_name = getattr(self, "_last_engine_name", "Unknown")
            engine_class = getattr(self, "_last_engine_class", "Unknown")
            engine_model = getattr(self, "_last_engine_model", "N/A")
            engine_voice = getattr(self, "_last_engine_voice", "N/A")
            engine_device = getattr(self, "_last_engine_device", "unknown")
            # V11.42.0: show GPU/CPU prominently
            device_tag = f" ({engine_device.upper()})" if engine_device != "unknown" else ""
            proof_path = Path(actual_path).with_suffix(".proof.txt")
            try:
                import datetime as _dt

                proof_content = f"""TTS Engine Proof File
=====================
Generated: {_dt.datetime.now().isoformat()}
Audio file: {Path(actual_path).name}

ENGINE USED: {engine_name}
Device: {engine_device}
Engine class: {engine_class}
Model path: {engine_model}
Voice: {engine_voice}

This file is DEFINITIVE PROOF of which engine generated the audio.
If this says VibeVoice with Device: cuda, the audio was generated by
VibeVoice on your GPU.
"""
                proof_path.write_text(proof_content, encoding="utf-8")
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

            from pathlib import Path as _P

            p = _P(actual_path)
            self.status_label.setText(f"✅ Audio saved to: {actual_path}")
            self.result_preview.setPlainText(
                f"🎙️ TTS Complete\n\n"
                f"Output file: {actual_path}\n"
                f"Engine: {engine_name}{device_tag}\n"
                f"File size: {p.stat().st_size // 1024} KB"
                if p.exists()
                else f"🎙️ TTS Complete\n\nOutput: {actual_path}"
            )
            self.result_preview.setVisible(True)
            self.again_btn.setVisible(True)
            from PySide6.QtCore import QTimer

            file_arg = str(p) if p.exists() else (str(p.parent) if str(p.parent) != "." else None)
            QTimer.singleShot(
                0,
                lambda: _show_success_modal(
                    self,
                    "🎙️ TTS Complete",
                    f"Engine: {engine_name}{device_tag}\nAudio saved to:\n{actual_path}",
                    file_path=file_arg,
                    on_try_another=self._on_try_another
                    if hasattr(self, "_on_try_another")
                    else None,
                ),
            )
        else:
            self.status_label.setText("❌ No output produced.")
            self.again_btn.setVisible(True)

    def _process(self, input_text: str, options: dict) -> str:
        """Generate TTS audio from text."""
        voice = options.get("voice", "")
        lang = options.get("language", "auto")
        style = options.get("style", "natural")

        # V11.34.1: log the EXACT voice being used so the user can verify.
        self._emit_progress(-1, f"🎙️ Voice: '{voice}' | Lang: {lang} | Style: {style}")

        # V11.35.0: apply speaking style — speed multiplier + emotion prefix.
        # V11.42.1: DON'T prepend text prefixes for ANY engine — VibeVoice
        # reads them literally, Kokoro reads them literally. Only use
        # speed adjustment. The style is passed to VibeVoiceEngine via
        # cfg_scale (handled in the engine itself).
        speed_mult, emotion_prefix = self._STYLE_PROFILES.get(
            style, self._STYLE_PROFILES["natural"]
        )
        synth_text = input_text  # V11.42.1: never prepend emotion prefix to text
        if speed_mult != 1.0:
            self._emit_progress(-1, f"🎙️ Style '{style}': speed={speed_mult}×")

        try:
            import tempfile
            from pathlib import Path as _P

            from utils.settings import Settings

            s = Settings()

            if lang == "auto":
                from core.tts.engine import detect_language

                detected = detect_language(input_text)
            else:
                detected = lang

            # V11.31.3: direct engine instantiation with fallback.
            # V11.34.0: Persian VITS support — if voice starts with "vits:",
            # use the PersianVitsEngine with the specified HF repo.
            # V11.36.0: Sherpa Persian support — if voice starts with "sherpa:",
            # use the SherpaPersianEngine with the specified voice ID.
            # V11.36.1: voice-prefix checks take PRIORITY over detected language
            # so the user's explicit voice choice is always respected.
            # V11.40.0: simplified engine selection — Kokoro (fast), VibeVoice (quality), Sherpa (Farsi).
            self._emit_progress(-1, f"🎙️ Engine selection: detected={detected}, voice={voice!r}")
            if voice and voice.startswith("vibevoice:"):
                # V11.43.1: VibeVoice for English (restored)
                voice_name = voice[len("vibevoice:") :]
                vv_path = s.get("tts.vibevoice_model_path", "")
                vv_voices = s.get("tts.vibevoice_voices_dir", "")
                if vv_path:
                    from core.tts.engine_cache import get_vibevoice_engine

                    self._emit_progress(-1, "🎙️ ═══ VIBEVOICE ENGINE SELECTED ═══")
                    self._emit_progress(-1, f"🎙️ Voice: {voice_name}")
                    engine = get_vibevoice_engine(
                        model_path=vv_path,
                        voices_dir=vv_voices,
                        default_voice=voice_name,
                        log_callback=lambda msg, level="INFO": (
                            self._emit_progress(-1, f"🎙️ {msg}") if level != "DEBUG" else None
                        ),
                    )
                    voice_for_engine = voice_name
                    self._last_engine_name = "VibeVoice"
                    self._last_engine_class = type(engine).__name__
                    self._last_engine_model = vv_path
                    self._last_engine_voice = voice_name
                    self._last_engine_device = getattr(engine, "get_device", lambda: "unknown")()
                else:
                    self._emit_progress(-1, "🎙️ ⚠️ VibeVoice path not set, using Kokoro")
                    from core.tts.engine_cache import get_kokoro_engine

                    engine = get_kokoro_engine(log_callback=lambda msg, level="INFO": None)
                    # V0.6.0 (T1): a "vibevoice:…" id is not a Kokoro voice —
                    # passing it through made the advertised Kokoro fallback fail
                    # on the unknown voice instead of falling back. Drop it and
                    # let Kokoro use its own default voice.
                    voice_for_engine = None
                    self._last_engine_name = "Kokoro (fallback)"
                    self._last_engine_class = type(engine).__name__
                    self._last_engine_model = "kokoro-pipeline"
                    self._last_engine_voice = voice
                    # V11.46.0: Kokoro is GPU-only (device='cuda' in KPipeline)
                    self._last_engine_device = "cuda" if _tts_cuda_available() else "cpu-blocked"
            elif detected == "fa":
                # V11.44.0: Farsi default: Kokoro
                from core.tts.engine_cache import get_kokoro_engine

                self._emit_progress(-1, "🎙️ Using Kokoro (default Farsi)")
                engine = get_kokoro_engine(log_callback=lambda msg, level="INFO": None)
                voice_for_engine = voice or "af_heart"
                self._last_engine_name = "Kokoro"
                self._last_engine_class = type(engine).__name__
                self._last_engine_model = "kokoro-pipeline"
                self._last_engine_voice = voice or "af_heart"
                # V11.46.0: Kokoro is GPU-only (device='cuda' in KPipeline)
                self._last_engine_device = "cuda" if _tts_cuda_available() else "cpu-blocked"
            else:
                # English default: Kokoro (fast)
                from core.tts.engine_cache import get_kokoro_engine

                self._emit_progress(-1, "🎙️ Using Kokoro (fast)")
                engine = get_kokoro_engine(log_callback=lambda msg, level="INFO": None)
                voice_for_engine = voice
                self._last_engine_name = "Kokoro"
                self._last_engine_class = type(engine).__name__
                self._last_engine_model = "kokoro-pipeline"
                self._last_engine_voice = voice or "af_heart"
                # V11.46.0: Kokoro is GPU-only (device='cuda' in KPipeline)
                self._last_engine_device = "cuda" if _tts_cuda_available() else "cpu-blocked"

            # V11.31.7: DO NOT split into paragraphs — call engine.synthesize()
            # ONCE with the full text. NeuTTS does its own internal chunking
            # via _split_long_line. Splitting externally breaks NeuTTS
            # (phonemizer mismatches on short fragments) and causes the
            # "9/18 then failed" issue.
            # No Kokoro fallback — voice quality must stay consistent.
            # V11.42.1: pass style to engine for cfg_scale control
            tmp_path = _P(tempfile.mktemp(suffix=".wav"))
            self._emit_progress(-1, f"🎙️ Synthesizing… ({detected})")
            # VibeVoiceEngine accepts a 'style' param; other engines ignore it
            try:
                result = engine.synthesize(
                    synth_text, tmp_path, voice_for_engine or None, speed_mult, style=style
                )
            except TypeError:
                # Engine doesn't accept 'style' param — call without it
                result = engine.synthesize(
                    synth_text, tmp_path, voice_for_engine or None, speed_mult
                )

            if result and Path(result).exists():
                self._emit_progress(100, "✅ TTS complete")
                return str(result)
            else:
                # V11.31.11: synthesize returned None — check engine.last_error.
                err = getattr(engine, "last_error", "unknown error")
                self._emit_progress(100, f"❌ TTS failed: {err}")
                return f"Error: TTS engine failed: {err}"
        except Exception as e:
            return f"Error: {e}"
