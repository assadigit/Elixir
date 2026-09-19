"""V11.36.0: Persian TTS via sherpa-onnx — high-quality local Farsi TTS.

Uses the ``sherpa_onnx`` Python package to run VITS models trained for
Persian/Farsi. This is the same engine used by the
``karim23657/Persian-TTS-sherpa`` HuggingFace Space.

The models are Piper/MMS/Coqui VITS models converted to ONNX format.
They're downloaded from the sherpa-onnx GitHub releases on first use
and cached locally.

Available voices (with Persian names from the Space):
  - 💧 نیما (Nima)     — vits-piper-fa-gyro-medium    [USER'S FAVORITE]
  - ⚡️ آریا (Aria)     — vits-piper-fa-amir-medium
  - 🌠 راد (Rad)       — MMS fa (Facebook MMS-TTS)
  - 🌹 ریما (Rima)     — vits-mimic3-fa-haaniye_low
  - 🌠 پیام (Payam)    — vits-piper-fa_en-rezahedayatfar-ibrahimwalk-medium
  - 🚀 برنا (Barna)    — vits-piper-fa-ganji

Install:
  pip install sherpa-onnx
  pip install soundfile numpy
"""

from __future__ import annotations

import logging
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

from core.tts.engine import LogFn, TTSEngine

logger = logging.getLogger(__name__)


# ── Voice catalog ──────────────────────────────────────────────────────
# Each entry: (voice_id, display_name, download_url, model_subdir)
# The model_subdir is the folder name inside the extracted tar.bz2.
SHERPA_PERSIAN_VOICES: list[tuple[str, str, str, str]] = [
    # The user's favorite — "نیما" (gyro Piper model)
    (
        "nima",
        "💧 نیما (Nima) — gyro",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fa_IR-gyro-medium.tar.bz2",
        "vits-piper-fa_IR-gyro-medium",
    ),
    # Other Piper voices
    (
        "aria",
        "⚡️ آریا (Aria) — amir",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fa_IR-amir-medium.tar.bz2",
        "vits-piper-fa_IR-amir-medium",
    ),
    (
        "payam",
        "🌠 پیام (Payam) — bilingual fa/en",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fa_en-rezahedayatfar-ibrahimwalk-medium.tar.bz2",
        "vits-piper-fa_en-rezahedayatfar-ibrahimwalk-medium",
    ),
    (
        "rima",
        "🌹 ریما (Rima) — mimic3 haaniye",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-mimic3-fa-haaniye_low.tar.bz2",
        "vits-mimic3-fa-haaniye_low",
    ),
]

# espeak-ng-data is needed for phonemization of Piper models.
_ESPEAK_NG_DATA_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/espeak-ng-data.tar.bz2"
)
_ESPEAK_NG_DATA_SUBDIR = "espeak-ng-data"


def _default_model_dir() -> Path:
    """Where to cache downloaded sherpa-onnx models."""
    return Path.home() / ".elixir" / "sherpa_persian_models"


def _download_and_extract(url: str, dest_dir: Path, log) -> Path:
    """Download a tar.bz2 and extract it to dest_dir. Returns dest_dir.

    If already extracted, skips the download.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Check if already extracted (look for any .onnx file).
    if dest_dir.exists() and any(dest_dir.rglob("*.onnx")):
        log(f"  ♻️ Model cached at: {dest_dir}", "DEBUG")
        return dest_dir

    log(f"  ⬇️ Downloading: {url}", "INFO")
    with tempfile.NamedTemporaryFile(suffix=".tar.bz2", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        urlretrieve(url, str(tmp_path))
        log(f"  📦 Extracting to: {dest_dir}", "INFO")
        with tarfile.open(str(tmp_path), "r:bz2") as tar:
            tar.extractall(str(dest_dir.parent))
    finally:
        tmp_path.unlink(missing_ok=True)
    return dest_dir


class SherpaPersianEngine(TTSEngine):
    """V11.36.0: Persian TTS via sherpa-onnx.

    Uses the ``sherpa_onnx`` Python package to run VITS models. The model
    is downloaded from the sherpa-onnx GitHub releases on first use
    (~60-100 MB) and cached locally.

    The "نیما" (Nima) voice is the user's favorite — it's the gyro Piper
    model, which produces natural-sounding Persian speech.
    """

    def __init__(
        self,
        voice_id: str = "nima",
        model_dir: Path | None = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._voice_id = voice_id
        self._model_dir = Path(model_dir) if model_dir else _default_model_dir()
        self._tts = None  # sherpa_onnx.OfflineTts instance
        self._espeak_data_dir = None
        self.last_error: str | None = None

    def _find_voice_entry(self) -> tuple[str, str, str, str] | None:
        """Find the voice entry for self._voice_id."""
        for entry in SHERPA_PERSIAN_VOICES:
            if entry[0] == self._voice_id:
                return entry
        return None

    def _ensure_model(self) -> None:
        """Download the model + espeak-ng-data if not cached, then load."""
        if self._tts is not None:
            return

        entry = self._find_voice_entry()
        if entry is None:
            raise ValueError(f"Unknown sherpa voice: {self._voice_id}")

        _vid, display_name, url, subdir = entry
        model_dir = self._model_dir / subdir

        # Download and extract the model.
        if not model_dir.exists() or not any(model_dir.rglob("*.onnx")):
            _download_and_extract(url, model_dir, self.log)

        # Find the .onnx file.
        onnx_files = list(model_dir.rglob("*.onnx"))
        if not onnx_files:
            raise FileNotFoundError(f"No .onnx file found in {model_dir}")
        model_onnx = onnx_files[0]

        # Find tokens.txt.
        tokens_files = list(model_dir.rglob("tokens.txt"))
        tokens_path = tokens_files[0] if tokens_files else None

        # Download espeak-ng-data (needed for Piper models).
        espeak_dir = self._model_dir / _ESPEAK_NG_DATA_SUBDIR
        if not espeak_dir.exists():
            _download_and_extract(_ESPEAK_NG_DATA_URL, espeak_dir, self.log)
        # Find the actual espeak-ng-data folder (it may be nested).
        espeak_data_dirs = list(self._model_dir.rglob("espeak-ng-data"))
        if espeak_data_dirs:
            self._espeak_data_dir = espeak_data_dirs[0]
        else:
            # Fallback: look for a folder with phoneme data.
            espeak_data_dirs = list(self._model_dir.rglob("phondata*"))
            if espeak_data_dirs:
                self._espeak_data_dir = espeak_data_dirs[0].parent

        self.log(f"  🔄 Loading sherpa-onnx Persian TTS: {display_name}", "INFO")
        self.log(f"     Model: {model_onnx.name}", "DEBUG")
        self.log(f"     Tokens: {tokens_path.name if tokens_path else 'N/A'}", "DEBUG")
        self.log(f"     Espeak: {self._espeak_data_dir}", "DEBUG")

        import sherpa_onnx

        kwargs = {
            "vits_model": str(model_onnx),
            "num_speakers": 1,
        }
        if tokens_path:
            kwargs["vits_tokens"] = str(tokens_path)
        if self._espeak_data_dir:
            kwargs["vits_data_dir"] = str(self._espeak_data_dir)

        self._tts = sherpa_onnx.OfflineTts(**kwargs)
        self.log("  ✅ Sherpa Persian TTS loaded", "INFO")

    def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Path | None:
        """Synthesize Persian text to a WAV file.

        Args:
            text: Persian text to synthesize.
            out_path: Path to save the WAV file.
            voice: Ignored (voice is set at construction time).
            speed: Speed multiplier (1.0 = normal).
        """
        if not text or not text.strip():
            return None
        try:
            self._ensure_model()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            self.log(
                f"  🎙️ Sherpa Persian [{self._voice_id}]: generating {len(text)} chars…", "INFO"
            )

            # sherpa_onnx generates audio as a list of float samples.
            audio_obj = self._tts.generate(text, sid=0, speed=speed)
            # The result has .samples and .sample_rate attributes.
            import numpy as np
            import soundfile as sf

            samples = np.array(audio_obj.samples, dtype=np.float32)
            sample_rate = audio_obj.sample_rate
            sf.write(str(out_path), samples, sample_rate)

            if out_path.exists():
                self.log("  ✅ Sherpa Persian TTS complete", "INFO")
                return out_path
            self.last_error = "No output file produced"
            return None
        except Exception as e:
            self.last_error = str(e)
            self.log(f"  ❌ Sherpa Persian error: {e}", "ERROR")
            logger.exception("SherpaPersianEngine.synthesize failed")
            return None
