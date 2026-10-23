"""V4.2.0: Text-to-Speech engine abstraction.

One interface, two backends (V0.6.64: the Piper binary engine was removed —
user decision, remaining-surface item 4):

* :class:`KokoroEngine` — English via the Kokoro Python API (generator that
  yields ``(graphemes, phonemes, audio)`` per chunk). Best open-weight EN TTS.
* :class:`CoquiTTSEngine` — V10.36.0 multilingual neural TTS (XTTS v2, voice
  cloning) — the Persian route of this legacy router. The modern TTS tool
  and the podcast generator route Farsi through Kokoro / Sherpa instead.

Language auto-routing: :func:`detect_language` inspects the Unicode script
of the text and returns ``"fa"`` for Persian (Arabic-script) text, ``"en"``
otherwise. :class:`TTSEngine.synthesize` routes to the right backend
automatically based on the detected language and the configured voices.

Both backends return a path to a ``.wav`` file, so callers
(:class:`core.outputs.podcast_audio.PodcastAudioGenerator`) can stitch
segments with :mod:`pydub` without caring which engine produced them.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

# V18.20.3.12 (F821): NeuTTSEngine is referenced only in annotations here
# (:486/:530); the runtime import stays lazy inside the ``neutts`` property
# because neutts_engine.py imports TTSEngine/LogFn from this module (circular).
if TYPE_CHECKING:
    from core.tts.neutts_engine import NeuTTSEngine

# pydub is used by the podcast generator, not here — but we keep the import
# lazy there to avoid a hard dependency at module load.


# ── Language detection ─────────────────────────────────────────────────────

# Arabic-script Unicode blocks used by Persian:
#   \u0600-\u06FF  Arabic
#   \u0750-\u077F  Arabic Supplement
#   \uFB50-\uFDFF  Arabic Presentation Forms-A
#   \uFE70-\uFEFF  Arabic Presentation Forms-B

logger = logging.getLogger(__name__)

_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def detect_language(text: str) -> str:
    """Return ``"fa"`` if ``text`` contains Arabic-script characters, else ``"en"``.

    Persian uses the Arabic script with a few extra letters (پ چ ژ گ)
    that all live in the Arabic Unicode block, so this simple check is
    sufficient for routing. Mixed-language lines are routed by majority,
    falling back to English when ambiguous.
    """
    if not text:
        return "en"
    arabic = len(_ARABIC_SCRIPT_RE.findall(text))
    # Threshold: if >20% of non-space chars are Arabic-script, treat as FA.
    non_space = max(len([c for c in text if not c.isspace()]), 1)
    if arabic / non_space > 0.2:
        return "fa"
    return "en"


# ── Engine base ────────────────────────────────────────────────────────────

LogFn = Callable[[str, str], None]


class TTSEngine:
    """Abstract TTS engine: text + voice → wav file path.

    Subclasses implement :meth:`_synthesize`. Callers use :meth:`synthesize`,
    which handles temp-file creation and error isolation.
    """

    def __init__(self, log_callback: LogFn | None = None) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.last_error: str | None = None

    def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Path | None:
        """Synthesize ``text`` to ``out_path`` (.wav).

        Returns ``out_path`` on success, ``None`` on failure (logged).
        On failure, ``self.last_error`` is set to the exception message so
        callers (e.g. the Preview UI) can show the actual error instead of
        a generic "could not generate" message.
        """
        self.last_error = None
        text = (text or "").strip()
        if not text:
            self.last_error = "empty text"
            self.log("  ⚠️ TTS: empty text, skipping", "DEBUG")
            return None
        try:
            self._synthesize(text, out_path, voice, speed)
            if out_path.exists() and out_path.stat().st_size > 44:
                return out_path
            self.last_error = "produced empty audio file"
            self.log(f"  ⚠️ TTS: produced empty audio for: {text[:60]}…", "WARNING")
            return None
        except Exception as e:
            self.last_error = str(e)
            self.log(f"  ⚠️ TTS synthesis failed: {e}", "WARNING")
            return None

    def _synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None,
        speed: float,
    ) -> None:
        raise NotImplementedError


# ── Kokoro (English) ───────────────────────────────────────────────────────


class KokoroEngine(TTSEngine):
    """English TTS via the Kokoro Python API.

    Kokoro's ``KPipeline`` is a generator yielding ``(graphemes, phonemes,
    audio)`` tuples per chunk. We concatenate the numpy audio arrays and
    write a single 24 kHz mono WAV.
    """

    def __init__(self, log_callback: LogFn | None = None) -> None:
        super().__init__(log_callback)
        self._pipeline = None  # lazy-loaded
        self._lang_code = "a"  # American English

    def _ensure_pipeline(self) -> None:
        """Lazy-load the Kokoro KPipeline. Prefers GPU, falls back to CPU.

        V11.45.0 forced ``device='cuda'`` and hard-failed if CUDA was
        unavailable. V11.46.1 relaxes this: the UI layer
        (``_guard_gpu_required`` in base_dialog.py) now handles the
        warn+confirm flow, so the engine itself should PREFER GPU but
        fall back to CPU with a prominent WARNING log — otherwise the
        user's "Yes, continue on CPU" confirmation is meaningless because
        the engine would still crash.

        Behaviour:
          1. If ``torch.cuda.is_available()`` → ``device='cuda'`` (fast).
          2. Else → ``device='cpu'`` + WARNING log with the install hint.
          3. Either way, verify the model params landed on the chosen
             device and log VRAM (GPU only).
        """
        if self._pipeline is None:
            import torch
            from kokoro import KPipeline  # heavy import, deferred

            cuda_ok = torch.cuda.is_available()
            if cuda_ok:
                device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                self.log(
                    f"  🔄 Loading Kokoro pipeline (EN) on GPU ({gpu_name})…",
                    "INFO",
                )
            else:
                device = "cpu"
                self.log(
                    "  ⚠️ CUDA NOT available — Kokoro will run on CPU "
                    "(~15x slower than GPU). To fix: pip install torch "
                    "--index-url https://download.pytorch.org/whl/cu126",
                    "WARNING",
                )

            t0 = time.time()
            # device= is the whole point — without it Kokoro defaults to
            # CPU silently. We pass it explicitly in both branches.
            self._pipeline = KPipeline(lang_code=self._lang_code, device=device)
            load_time = time.time() - t0

            # Verify the model actually lives on the expected device.
            try:
                model = getattr(self._pipeline, "model", None)
                if model is not None and hasattr(model, "parameters"):
                    dev = next(model.parameters()).device
                    cpu_params = sum(1 for p in model.parameters() if p.device.type == "cpu")
                    gpu_params = sum(1 for p in model.parameters() if p.device.type == "cuda")
                    vram_mb = torch.cuda.memory_allocated(0) // (1024 * 1024) if cuda_ok else 0
                    vram_str = f", {vram_mb} MB VRAM" if cuda_ok else ""
                    self.log(
                        f"  ✅ Kokoro ready in {load_time:.1f}s — model on "
                        f"{dev} ({gpu_params} GPU / {cpu_params} CPU params"
                        f"{vram_str})",
                        "DEBUG",
                    )
                    # If we wanted GPU but some params landed on CPU, force
                    # them up. (Only relevant when cuda_ok is True.)
                    if cuda_ok and cpu_params > 0:
                        self.log(
                            f"  ⚠️ {cpu_params} params still on CPU — forcing model.to('cuda')",
                            "WARNING",
                        )
                        model.to("cuda")
                else:
                    self.log(
                        f"  ✅ Kokoro ready in {load_time:.1f}s "
                        "(device verify skipped — no .model attribute)",
                        "DEBUG",
                    )
            except Exception as e:
                self.log(
                    f"  ✅ Kokoro ready in {load_time:.1f}s (device verify skipped: {e})",
                    "DEBUG",
                )

    def _synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None,
        speed: float,
    ) -> None:
        import numpy as np
        import soundfile as sf

        self._ensure_pipeline()
        voice = voice or "af_heart"
        # Kokoro's `speed` param: 1.0 = normal, >1 faster, <1 slower.
        parts = []
        for _gs, _ps, audio in self._pipeline(text, voice=voice, speed=float(speed)):
            # Kokoro yields audio as a torch.FloatTensor. If running on CUDA,
            # the tensor lives on GPU and np.asarray() fails with:
            #   "can't convert cuda:0 device type tensor to numpy"
            # Fix: move to CPU first, then convert to numpy.
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            else:
                audio = np.asarray(audio)
            parts.append(audio)
        if not parts:
            raise RuntimeError("Kokoro produced no audio chunks")
        audio = np.concatenate(parts)
        sf.write(str(out_path), audio, 24000)


# ── Router ─────────────────────────────────────────────────────────────────


class CoquiTTSEngine(TTSEngine):
    """V10.36.0: Coqui XTTS v2 — multilingual neural TTS with voice cloning.

    Supports Persian natively (V0.6.64: the only Persian route in this
    legacy router since the Piper removal). Uses the ``TTS`` library
    (pip install TTS). The model is ~1.8 GB and loads lazily on first use.

    Requires a GPU for good speed (~2x realtime on RTX 3060). Falls back
    to CPU if CUDA is unavailable (much slower).

    Configuration (in settings.json):
      tts.coqui_model: "tts_models/multilingual/multi-dataset/xtts_v2"
      tts.coqui_speaker: "Ana" (default speaker name)
      tts.coqui_voice_sample: "" (path to 6s WAV for voice cloning)

    Install:
      pip install TTS
      pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        speaker: str = "Ana",
        voice_sample_path: Path | None = None,
        device: str = "cuda",
        log_callback: LogFn | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._model_name = model_name
        self._speaker = speaker
        self._voice_sample = str(voice_sample_path) if voice_sample_path else ""
        self._device = device if self._cuda_available() else "cpu"
        self._tts = None

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    @property
    def _model(self):
        """Lazily load the Coqui TTS model (slow first time, ~10s)."""
        if self._tts is None:
            from TTS.api import TTS

            self.log(f"  🎙️ Loading Coqui XTTS v2 model on {self._device}…", "INFO")
            self._tts = TTS(self._model_name).to(self._device)
            self.log("  ✅ Coqui XTTS v2 loaded", "INFO")
        return self._tts

    def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Path | None:
        """Synthesize text to a WAV file using Coqui XTTS v2.

        Args:
            text: The text to synthesize.
            out_path: Path to save the WAV file.
            voice: Optional speaker name or voice-sample path override.
            speed: Speed multiplier (1.0 = normal).
        """
        if not text or not text.strip():
            return None
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Determine speaker
            speaker = voice or self._speaker
            voice_sample = None
            # If voice is a file path, use it for voice cloning
            if voice and Path(voice).exists():
                voice_sample = voice
                speaker = None  # cloning mode doesn't use speaker name
            elif self._voice_sample and Path(self._voice_sample).exists():
                voice_sample = self._voice_sample
                speaker = None

            # Detect language (Coqui supports "en", "fa", "ar", etc.)
            from core.tts.engine import detect_language

            lang = detect_language(text)

            kwargs = {
                "text": text,
                "language": lang,
                "file_path": str(out_path),
                "speed": max(0.5, min(2.0, speed)),
            }
            if voice_sample:
                kwargs["speaker_wav"] = voice_sample
            elif speaker:
                kwargs["speaker"] = speaker

            self._model.tts_to_file(**kwargs)
            self.log(f"  🎙️ Coqui: {len(text)} chars → {out_path.name} ({lang})", "DEBUG")
            return out_path
        except Exception as e:
            self.log(f"  ⚠️ Coqui TTS failed: {e}", "WARNING")
            return None


class TTSRouter:
    """Routes synthesis to the right engine based on detected language.

    V4.5.0: Supports three engines:
    * **English** → NeuTTS-Air (primary, voice-cloning) OR Kokoro (alternative,
      preset voices). Selected via the ``en_engine`` parameter.
    * **Persian** → Coqui XTTS v2 (V10.36.0; V0.6.64: the only Persian
      route — the Piper binary engine was removed entirely).

    All engines are lazy-loaded on first use to keep startup fast. Callers
    pass the script language explicitly (detected once per line by the
    podcast generator) so we don't re-detect per segment.
    """

    def __init__(
        self,
        en_engine: str = "neutts",
        neutts_gguf_path: Path | None = None,
        neutts_project_path: Path | None = None,
        coqui_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        coqui_speaker: str = "Ana",
        coqui_voice_sample: str = "",
        log_callback: LogFn | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._kokoro: KokoroEngine | None = None
        self._neutts: NeuTTSEngine | None = None
        self._coqui: CoquiTTSEngine | None = None
        self._en_engine = en_engine  # "neutts" or "kokoro"
        self._neutts_gguf_path = neutts_gguf_path
        self._neutts_project_path = neutts_project_path
        self._coqui_model = coqui_model
        self._coqui_speaker = coqui_speaker
        self._coqui_voice_sample = coqui_voice_sample

    @property
    def kokoro(self) -> KokoroEngine:
        if self._kokoro is None:
            self._kokoro = KokoroEngine(log_callback=self.log)
        return self._kokoro

    @property
    def coqui(self) -> CoquiTTSEngine:
        """V10.36.0: Lazily load the Coqui XTTS v2 engine."""
        if self._coqui is None:
            voice_sample = Path(self._coqui_voice_sample) if self._coqui_voice_sample else None
            self._coqui = CoquiTTSEngine(
                model_name=self._coqui_model,
                speaker=self._coqui_speaker,
                voice_sample_path=voice_sample,
                log_callback=self.log,
            )
        return self._coqui

    @property
    def neutts(self) -> NeuTTSEngine:
        """Lazily load the NeuTTS-Air engine (slow first time)."""
        if self._neutts is None:
            from core.tts.neutts_engine import NeuTTSEngine

            if self._neutts_gguf_path is None or self._neutts_project_path is None:
                raise RuntimeError(
                    "NeuTTS paths not configured. Set tts.neutts_gguf_path "
                    "and tts.neutts_project_path in Settings → TTS."
                )
            self._neutts = NeuTTSEngine(
                gguf_path=self._neutts_gguf_path,
                neutts_project_path=self._neutts_project_path,
                log_callback=self.log,
            )
        return self._neutts

    def english_engine(self) -> TTSEngine:
        """Return the configured English engine (NeuTTS or Kokoro)."""
        if self._en_engine == "kokoro":
            return self.kokoro
        # Default: NeuTTS. If it fails to load, fall back to Kokoro.
        try:
            return self.neutts
        except Exception as e:
            self.log(
                f"  ⚠️ NeuTTS unavailable ({e}), falling back to Kokoro",
                "WARNING",
            )
            return self.kokoro

    def persian_engine(self) -> TTSEngine:
        """Return the Persian engine — Coqui XTTS v2.

        V10.36.0 made Coqui the quality route with a Piper fallback;
        V0.6.64 removed Piper entirely, so Coqui is the only Persian engine
        in this legacy router. Construction is cheap (the ~1.8 GB model
        loads lazily on first use); synthesis failures stay fail-soft
        (``TTSEngine.synthesize`` → ``last_error`` + ``None``).
        """
        return self.coqui

    def synthesize(
        self,
        text: str,
        out_path: Path,
        language: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Path | None:
        """Synthesize using the right engine for the language AND voice.

        V4.7.13: If the voice is a Kokoro preset (e.g., af_heart) but the
        engine is NeuTTS, route to Kokoro for that segment. This handles
        the "distinct voices" case where Host B uses a Kokoro voice while
        Host A uses NeuTTS.
        V10.36.0: Persian routes to Coqui XTTS v2 (V0.6.64: Coqui only —
        the Piper fallback is gone with the engine).
        """
        from core.tts.voices import KOKORO_VOICES

        kokoro_ids = {v[0] for v in KOKORO_VOICES}

        if language == "fa":
            engine = self.persian_engine()
        elif voice and voice in kokoro_ids:
            # Voice is a Kokoro preset — use Kokoro even if engine is NeuTTS
            engine = self.kokoro
        else:
            engine = self.english_engine()
        return engine.synthesize(text, out_path, voice, speed)
