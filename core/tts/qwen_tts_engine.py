"""V11.38.0: Qwen3-TTS engine — replaces NeuTTS for English TTS.

Uses the ``qwen_tts`` Python package to run Qwen3-TTS-12Hz-1.7B-CustomVoice.
This model supports:
  - 10 languages (English, Chinese, Japanese, Korean, German, French,
    Russian, Portuguese, Spanish, Italian)
  - 9 premium speaker voices (queryable at runtime via get_supported_speakers)
  - Emotion/style control via ``instruct`` parameter
  - Voice cloning (Base model only — CustomVoice uses named speakers)

The model loads from a local directory path (no download at runtime).

Install:
  pip install qwen-tts
  (optional) pip install flash-attn --no-build-isolation

Settings:
  tts.qwen_model_path: path to the local model folder
  tts.qwen_speaker: default speaker name (e.g. "Vivian")
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.tts._json_subprocess import PersistentJsonSubprocess
from core.tts.engine import LogFn, TTSEngine

logger = logging.getLogger(__name__)

# V18.20.4.4 (W-c2/W-c11): timeout bounds as module constants — testable
# seams (the values are UNCHANGED from the old inline literals; no cap
# changes). The shared base makes both timeouts REAL: a silent-but-alive
# child can no longer block a readline() past the deadline.
QWEN_LOAD_TIMEOUT_S = 120   # was the inline `120` in _ensure_model
QWEN_CHUNK_TIMEOUT_S = 120  # was the inline `120` in _run_subprocess


# V11.38.6: All 9 premium speakers from the Qwen3-TTS-12Hz-1.7B-CustomVoice model.
# Source: official model card on HuggingFace.
# Each entry: (speaker_name, description, native_language)
QWEN_TTS_KNOWN_SPEAKERS = [
    "Vivian",     # Bright, slightly edgy young female voice. Chinese.
    "Serena",     # Warm, gentle young female voice. Chinese.
    "Uncle_Fu",   # Seasoned male voice with a low, mellow timbre. Chinese.
    "Dylan",      # Youthful Beijing male voice with a clear, natural timbre. Chinese (Beijing Dialect).
    "Eric",       # Lively Chengdu male voice with a slightly husky brightness. Chinese (Sichuan Dialect).
    "Ryan",       # Dynamic male voice with strong rhythmic drive. English.
    "Aidan",      # Sunny American male voice with a clear midrange. English.
    "Ono_Anna",   # Playful Japanese female voice with a light, nimble timbre. Japanese.
    "Sohee",      # Warm Korean female voice with rich emotion. Korean.
]

# Speaker descriptions for the UI
QWEN_TTS_SPEAKER_INFO = {
    "Vivian":    ("Female", "Bright, slightly edgy young female voice", "Chinese"),
    "Serena":    ("Female", "Warm, gentle young female voice", "Chinese"),
    "Uncle_Fu":  ("Male",   "Seasoned male voice with a low, mellow timbre", "Chinese"),
    "Dylan":     ("Male",   "Youthful Beijing male voice, clear natural timbre", "Chinese (Beijing)"),
    "Eric":      ("Male",   "Lively Chengdu male voice, slightly husky", "Chinese (Sichuan)"),
    "Ryan":      ("Male",   "Dynamic male voice with strong rhythmic drive", "English"),
    "Aidan":     ("Male",   "Sunny American male voice with clear midrange", "English"),
    "Ono_Anna":  ("Female", "Playful Japanese female voice, light nimble", "Japanese"),
    "Sohee":     ("Female", "Warm Korean female voice with rich emotion", "Korean"),
}

# Supported languages (from the model card)
QWEN_TTS_LANGUAGES = [
    "English", "Chinese", "Japanese", "Korean", "German",
    "French", "Russian", "Portuguese", "Spanish", "Italian",
]


class QwenTtsEngine(TTSEngine):
    """V11.38.0: Qwen3-TTS engine for English (and 9 other languages).

    Replaces NeuTTS. Uses the ``qwen_tts`` package with a local model path.
    The model loads once and stays in VRAM (via the engine cache).
    """

    def __init__(
        self,
        model_path: str = "",
        speaker: str = "Vivian",
        language: str = "English",
        device: str = "cuda",
        log_callback: LogFn | None = None,
    ) -> None:
        super().__init__(log_callback)
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._model_path = model_path
        self._speaker = speaker
        self._language = language
        # V11.38.2: properly detect CUDA with logging
        cuda_ok = self._cuda_available()
        self._device = device if (device == "cuda" and cuda_ok) else "cpu"
        if device == "cuda" and not cuda_ok:
            self.log("  ⚠️ CUDA requested but not available — using CPU (SLOW)", "WARNING")
        else:
            self.log(f"  ℹ️ Qwen3-TTS device: {self._device}", "INFO")
        self._model = None  # marks subprocess as running (True = loaded)
        self._sub: PersistentJsonSubprocess | None = None  # V18.20.4.4 (O-c2)
        self._available_speakers: list[str] = []
        self.last_error: str | None = None

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            avail = torch.cuda.is_available()
            count = torch.cuda.device_count() if avail else 0
            return bool(avail and count > 0)
        except ImportError:
            return False
        except Exception:
            return False

    @staticmethod
    def _flash_attn_available() -> bool:
        """V11.38.1: properly check if flash_attn is actually usable.

        V11.38.3: disabled by default — flash_attn can cause hangs with
        Qwen3-TTS in some environments. Enable only via env var
        QWEN_TTS_USE_FLASH_ATTN=1.
        """
        import os
        if os.environ.get("QWEN_TTS_USE_FLASH_ATTN", "0") != "1":
            return False
        try:
            import flash_attn  # noqa: F401
            import torch
            if torch.cuda.is_available():
                major, _ = torch.cuda.get_device_capability()
                return major >= 8
            return False
        except ImportError:
            return False
        except Exception:
            return False

    def _ensure_model(self) -> None:
        """V11.38.6: Start the persistent subprocess and load the model.

        The subprocess stays alive across multiple generation calls,
        keeping the model in VRAM. This is 10x faster than reloading
        per chunk.

        V18.20.4.4 (O-c2/W-c2): ported onto the shared
        ``PersistentJsonSubprocess`` base — REAL timeouts (a silent child
        can no longer block the ready handshake forever) and the neutts
        kill-before-raise contract on every load failure.
        """
        if self._model is not None:
            return  # subprocess already running

        if not self._model_path:
            raise ValueError(
                "Qwen3-TTS model path not set. Configure it in "
                "Settings → TTS → Qwen3-TTS model path.")

        model_dir = Path(self._model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Qwen3-TTS model folder not found: {model_dir}")

        import os
        import sys

        script_path = str(Path(__file__).parent / "_qwen_tts_subprocess.py")
        self.log("  🔄 Starting Qwen3-TTS persistent subprocess...", "INFO")

        # Start the subprocess
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"

        sub = PersistentJsonSubprocess(
            name="Qwen3-TTS", log=self.log,
            stderr_prefix="[qwen-sub]", stderr_level="DEBUG")
        sub.spawn([sys.executable, script_path], env=env)
        self._sub = sub

        # Send the load command
        if not sub.send({"action": "load", "model_path": str(model_dir)}):
            self._kill_subprocess("cannot send load command")
            raise RuntimeError(
                "Qwen3-TTS subprocess not accepting the load command")

        # Wait for "ready" response (timeout 120s for model loading — a
        # REAL timeout now: the base's queue-based reader thread means a
        # silent-but-alive child cannot block the handshake forever)
        import time
        start = time.time()
        while True:
            remaining = QWEN_LOAD_TIMEOUT_S - (time.time() - start)
            if remaining <= 0:
                break
            msg = sub.read_json(remaining)
            if msg is None:
                break
            status = msg.get("status", "")
            if status == "loading":
                self.log(f"  🔄 Model loading (device: {msg.get('device', '?')})...", "INFO")
            elif status == "ready":
                self._device = msg.get("device", self._device)
                speakers = msg.get("speakers", [])
                if speakers:
                    self._available_speakers = speakers
                self.log(f"  ✅ Qwen3-TTS ready on {self._device}", "INFO")
                self.log(f"     Speakers: {len(self._available_speakers)} available", "INFO")
                self._model = True
                return
            elif status == "error":
                # V18.20.4.4 (W-c2): a reported load error can leave the
                # subprocess alive — kill before raising so VRAM is freed
                # (the neutts cleanup-before-raise pattern).
                self._kill_subprocess(
                    f"load error: {msg.get('error', 'unknown')}")
                raise RuntimeError(f"Model load failed: {msg.get('error', 'unknown')}")

        # V18.20.4.4 (W-c2): kill the still-loading subprocess instead of
        # dropping the Popen handle (previously the not-ready path nulled
        # the handle and raised
        # — the handle was dropped WITHOUT terminate/kill, so a
        # still-loading 1.7B model kept running and holding VRAM with no
        # reference left to kill it with; T-c1: the orphaned GPU lock
        # cascades into misleading "TTS failed" errors on the next
        # engine start).
        if sub.eof or not sub.alive:
            self._kill_subprocess("stdout closed during model load")
        else:
            self._kill_subprocess(
                f"model load not ready (timeout, {QWEN_LOAD_TIMEOUT_S}s)")
        raise RuntimeError("Qwen3-TTS subprocess failed to load model (timeout)")

    def get_available_speakers(self) -> list[str]:
        """Return the list of available speaker names.

        V11.38.1: returns the full 9-speaker list immediately (no need
        to load the model first). If the model is loaded and reports
        different speakers, we use those.
        """
        if self._available_speakers:
            return self._available_speakers
        # Return the known list immediately (don't trigger model load)
        return list(QWEN_TTS_KNOWN_SPEAKERS)

    def _split_text(self, text: str, max_chars: int = 200) -> list[str]:
        """V11.38.4: Split text into sentence-sized chunks for generation.

        Qwen3-TTS is autoregressive — long text takes exponentially longer.
        Splitting into sentences (max ~200 chars each) keeps each generation
        fast (5-10s on GPU per chunk).
        """
        import re
        text = text.strip()
        if len(text) <= max_chars:
            return [text] if text else []

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[\.!?؟\n])\s+', text)
        chunks = []
        current = ""
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) + 1 <= max_chars:
                current = (current + " " + sent).strip() if current else sent
            else:
                if current:
                    chunks.append(current)
                # If the sentence itself is too long, split on commas
                if len(sent) > max_chars:
                    parts = sent.split(",")
                    for part in parts:
                        part = part.strip()
                        if part:
                            chunks.append(part)
                else:
                    current = sent
        if current:
            chunks.append(current)
        return chunks

    def _run_subprocess(self, text: str, speaker: str, out_path: str) -> bool:
        """V11.38.6: Send a generate command to the persistent subprocess.

        The model is already loaded — this just generates one chunk.

        V18.20.4.4 (W-c11): the 120s per-chunk timeout is now REAL (the
        shared base's queue-based reader — a silent-but-alive child can no
        longer block a readline() past the deadline, which is exactly the
        T-c6 wedge), and a timed-out/dead chunk KILLS + RESETS the
        subprocess so its stale JSON response is never consumed by the
        NEXT command (protocol resync).
        """
        sub = self._sub
        if sub is None or not sub.alive:
            self.log("  ❌ Subprocess not running", "ERROR")
            return False

        # Send generate command
        ok = sub.send({
            "action": "generate",
            "text": text,
            "speaker": speaker,
            "language": self._language,
            "out_path": str(out_path),
        })
        if not ok:
            # send() already logged the reason (dead child / broken pipe).
            # V18.20.4.4 (W-c11): reap + reset so the engine recovers on
            # the next synthesize() call.
            self._kill_subprocess("send failed (subprocess gone)")
            return False

        # Wait for response (timeout 120s per chunk — REAL timeout, see
        # the docstring)
        import time
        start = time.time()
        while True:
            remaining = QWEN_CHUNK_TIMEOUT_S - (time.time() - start)
            if remaining <= 0:
                break
            msg = sub.read_json(remaining)
            if msg is None:
                break
            status = msg.get("status", "")
            if status == "generating":
                self.log(f"  ⏳ Generating ({msg.get('text_len', '?')} chars)...", "INFO")
            elif status == "ok":
                self.log(f"  ✅ Generated {msg.get('duration', '?')}s audio", "INFO")
                return True
            elif status == "error":
                # A reported generation error is a terminal response to OUR
                # command — the protocol stays in sync, so NO kill here
                # (bounded change).
                self.log(f"  ❌ Generation error: {msg.get('error', 'unknown')}", "ERROR")
                return False

        if sub.eof or not sub.alive:
            self.log("  ❌ Subprocess closed unexpectedly", "ERROR")
            # V18.20.4.4 (W-c11): reap the dead handle and reset the loaded
            # marker. Previously the dead handle was left in place with the
            # loaded marker still True, so every later synthesize() skipped
            # _ensure_model() and failed with "Subprocess not running" — a
            # permanently bricked engine until object GC.
            self._kill_subprocess("stdout closed mid-generation")
            return False

        self.log(
            f"  ❌ Subprocess timed out ({QWEN_CHUNK_TIMEOUT_S}s per chunk)",
            "ERROR")
        # V18.20.4.4 (W-c11): a timed-out chunk leaves the subprocess
        # mid-generation — its stale JSON response ("ok"/"error" for the
        # command that already gave up) would be consumed by the NEXT
        # command → protocol desync → cascading mis-attributed failures
        # (T-c6: one slow chunk can kill a whole podcast's audio). Kill +
        # reset so the remaining chunks in this batch fail fast
        # ("Subprocess not running" — bounded failure, no 120s hang per
        # chunk) and the NEXT synthesize() call reloads a fresh, in-sync
        # subprocess via _ensure_model().
        self._kill_subprocess(
            f"chunk timeout ({QWEN_CHUNK_TIMEOUT_S}s per chunk)")
        return False

    def _kill_subprocess(self, reason: str = "") -> None:
        """V18.20.4.4 (W-c2/W-c11): hard-kill the persistent subprocess.

        Used when the subprocess is wedged (load timeout, per-chunk
        timeout, stdout closed) — states where the graceful ``quit``
        handshake of ``_cleanup()`` would never be processed. Delegates
        the kill/reap to the shared base (``PersistentJsonSubprocess.kill``
        — the same contract as ``VibeVoiceEngine._kill_subprocess`` since
        V11.55.0). Resets ``self._sub``/``self._model`` so the next
        ``_ensure_model()`` starts fresh and the JSON protocol stays in
        sync (W-c11).
        """
        sub = self._sub
        if sub is not None:
            sub.kill(reason)
        self._sub = None
        self._model = None

    def _cleanup(self) -> None:
        """V11.38.6: Clean up the subprocess (graceful quit → kill)."""
        sub = self._sub
        if sub is not None:
            sub.close()
        self._sub = None
        self._model = None

    def __del__(self):
        try:
            self._cleanup()
        except Exception:
            logger.debug("best-effort op failed [qwen_tts_engine:__del__:L351]", exc_info=True)

    def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Path | None:
        """Synthesize text to a WAV file using Qwen3-TTS.

        V11.38.5: runs generation in a SUBPROCESS (not a thread) to avoid
        CUDA deadlock. Splits long text into chunks and generates each
        in a separate subprocess call.

        Args:
            text: Text to synthesize.
            out_path: Path to save the WAV file.
            voice: Speaker name (e.g. "Vivian", "Aidan"). Falls back to default.
            speed: Ignored (Qwen3-TTS doesn't have a speed param).
        """
        if not text or not text.strip():
            return None
        try:
            self._ensure_model()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Strip "qwen:" prefix if present
            speaker = voice or self._speaker
            if speaker and speaker.startswith("qwen:"):
                speaker = speaker[len("qwen:"):]

            # Split into chunks for faster generation
            chunks = self._split_text(text, max_chars=200)
            if not chunks:
                return None

            self.log(
                f"  🎙️ Qwen3-TTS: {len(text)} chars in {len(chunks)} chunks "
                f"(speaker={speaker})...", "INFO")

            import tempfile
            from pathlib import Path as _P

            if len(chunks) == 1:
                # Single chunk — generate via subprocess
                if self._run_subprocess(chunks[0], speaker, str(out_path)):
                    if out_path.exists():
                        self.log("  ✅ Qwen3-TTS complete", "INFO")
                        return out_path
                return None
            else:
                # Multiple chunks — generate each via subprocess, then stitch
                chunk_paths = []
                with tempfile.TemporaryDirectory(prefix="qwen_tts_") as tmp:
                    for i, chunk in enumerate(chunks):
                        self.log(
                            f"  ⏳ Chunk {i+1}/{len(chunks)} "
                            f"({len(chunk)} chars)...", "INFO")
                        cp = _P(tmp) / f"chunk_{i:03d}.wav"
                        if self._run_subprocess(chunk, speaker, str(cp)):
                            if cp.exists():
                                chunk_paths.append(cp)
                                self.log(f"  ✅ Chunk {i+1} done", "INFO")
                            else:
                                self.log(f"  ⚠️ Chunk {i+1} file missing", "WARNING")
                        else:
                            self.log(f"  ⚠️ Chunk {i+1} failed", "WARNING")

                    if not chunk_paths:
                        self.last_error = "All chunks failed"
                        return None

                    # Stitch chunks with 150ms silence
                    import numpy as np
                    import soundfile as sf
                    self.log(f"  🔗 Stitching {len(chunk_paths)} chunks...", "INFO")
                    audio_parts = []
                    for cp in chunk_paths:
                        data, sr = sf.read(str(cp))
                        audio_parts.append(data)
                    silence = np.zeros(int(sr * 0.15), dtype=audio_parts[0].dtype)
                    stitched = []
                    for i, part in enumerate(audio_parts):
                        if i > 0:
                            stitched.append(silence)
                        stitched.append(part)
                    final_audio = np.concatenate(stitched)
                    sf.write(str(out_path), final_audio, sr)
                    if out_path.exists():
                        self.log(
                            f"  ✅ Qwen3-TTS complete: "
                            f"{len(final_audio)/sr:.1f}s audio", "INFO")
                        return out_path

            self.last_error = "No audio produced"
            return None
        except Exception as e:
            self.last_error = str(e)
            self.log(f"  ❌ Qwen3-TTS error: {e}", "ERROR")
            logger.exception("QwenTtsEngine.synthesize failed")
            return None
