"""V11.34.0: Persian VITS TTS engine — high-quality local Farsi TTS.

Uses the Coqui TTS library to load VITS models trained specifically for
Persian/Farsi. These models are MUCH better than Piper's robotic Farsi
voices.

Supported models (all on HuggingFace):
  - ``karim23657/persian-tts-female-GPTInformal-Persian-vits`` (best, female)
  - ``Kamtera/persian-tts-female-vits`` (female)
  - ``Kamtera/persian-tts-male-vits`` (male)

The models use the ``Synthesizer`` API from ``TTS.utils.synthesizer``.
The model files (``config.json`` + ``model.pth``) are downloaded from
HuggingFace on first use and cached locally.

Install:
  pip install TTS
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.tts.engine import LogFn, TTSEngine

logger = logging.getLogger(__name__)


# Catalog of available Persian VITS models.
# Each entry: (model_id, huggingface_repo, description, gender)
PERSIAN_VITS_MODELS = [
    (
        "karim-female-best",
        "karim23657/persian-tts-female-GPTInformal-Persian-vits",
        "Best quality — trained on GPTInformal-Persian dataset",
        "Female",
    ),
    ("kamtera-female", "Kamtera/persian-tts-female-vits", "Good quality female voice", "Female"),
    ("kamtera-male", "Kamtera/persian-tts-male-vits", "Male voice", "Male"),
]


def _default_model_dir() -> Path:
    """Where to cache downloaded Persian VITS models."""
    from utils.settings import user_data_dir  # lazy: leaf stays app-free

    return user_data_dir() / "persian_vits_models"


class PersianVitsEngine(TTSEngine):
    """V11.34.0: High-quality Persian TTS via VITS models.

    Uses the Coqui TTS ``Synthesizer`` to load VITS models trained on
    Persian datasets. These produce far better Farsi speech than Piper.

    The model is downloaded from HuggingFace on first use (~100-200 MB)
    and cached locally for subsequent runs.
    """

    def __init__(
        self,
        model_repo: str = "karim23657/persian-tts-female-GPTInformal-Persian-vits",
        model_dir: Path | None = None,
        device: str = "cuda",
        log_callback: LogFn | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._model_repo = model_repo
        self._model_dir = Path(model_dir) if model_dir else _default_model_dir()
        self._device = device if self._cuda_available() else "cpu"
        self._synthesizer = None
        self._config_path = None
        self._model_path = None
        self.last_error: str | None = None

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
        except Exception:
            return False

    def _ensure_model(self) -> None:
        """Download the model from HuggingFace if not cached, then load it."""
        if self._synthesizer is not None:
            return

        from huggingface_hub import snapshot_download

        self._model_dir.mkdir(parents=True, exist_ok=True)

        # The model repo name (last segment) is used as the local folder.
        repo_short = self._model_repo.split("/")[-1]
        local_dir = self._model_dir / repo_short

        if not local_dir.exists() or not any(local_dir.iterdir()):
            self.log(f"  ⬇️ Downloading Persian VITS model: {self._model_repo}…", "INFO")
            snapshot_download(
                repo_id=self._model_repo,
                local_dir=str(local_dir),
            )
            self.log(f"  ✅ Model cached at: {local_dir}", "INFO")

        # Find config.json and model file.
        config_path = local_dir / "config.json"
        if not config_path.exists():
            # Some repos nest files — search for config.json.
            configs = list(local_dir.rglob("config.json"))
            if configs:
                config_path = configs[0]
            else:
                raise FileNotFoundError(f"config.json not found in {local_dir}")

        model_path = None
        for pattern in ("*.pth", "*.pt", "*.ckpt"):
            files = list(local_dir.rglob(pattern))
            if files:
                model_path = files[0]
                break
        if model_path is None:
            raise FileNotFoundError(f"No model file (.pth/.pt/.ckpt) found in {local_dir}")

        self._config_path = config_path
        self._model_path = model_path

        self.log(f"  🔄 Loading Persian VITS model on {self._device}…", "INFO")
        self.log(f"     Config: {config_path.name}", "DEBUG")
        self.log(f"     Model:  {model_path.name}", "DEBUG")

        from TTS.utils.synthesizer import Synthesizer

        self._synthesizer = Synthesizer(
            tts_checkpoint=str(model_path),
            tts_config_path=str(config_path),
            use_cuda=(self._device == "cuda"),
        )
        self.log("  ✅ Persian VITS model loaded", "INFO")

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
            voice: Ignored (VITS models are single-speaker).
            speed: Speed multiplier (1.0 = normal).
        """
        if not text or not text.strip():
            return None
        try:
            self._ensure_model()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            self.log(
                f"  🎙️ Persian VITS [{self._device.upper()}]: generating {len(text)} chars…", "INFO"
            )

            # VITS synthesizer returns a numpy array.
            wavs = self._synthesizer.tts(text, speaker_name=None, language_name="fa")
            self._synthesizer.save_wav(wavs, str(out_path))

            if out_path.exists():
                self.log("  ✅ Persian TTS complete", "INFO")
                return out_path
            self.last_error = "No output file produced"
            return None
        except Exception as e:
            self.last_error = str(e)
            self.log(f"  ❌ Persian VITS error: {e}", "ERROR")
            logger.exception("PersianVitsEngine.synthesize failed")
            return None
