"""Success / notification sounds — synthesised at runtime, no binary assets.

We generate a short, pleasant two-note rising chime (C5 → E5 → G5 major
triad arpeggio) as a 16-bit PCM WAV in memory and play it via Qt's
``QSoundEffect`` (low-latency, runs on the UI thread without blocking).
The WAV is cached on disk under ``~/.elixir/sounds/`` so it's only
synthesised once.

If audio output is unavailable (headless server, no audio device), the call
silently no-ops — never crashes the conversion-finish handler.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

_SOUNDS_DIR = Path.home() / ".elixir" / "sounds"


def _synth_chime(path: Path, notes=(523.25, 659.25, 783.99), note_ms=180, sr=44100) -> None:
    """Synthesise a gentle major-triad arpeggio into ``path`` as 16-bit WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    total = int(sr * (len(notes) * note_ms / 1000.0))
    frames = bytearray()
    for i, freq in enumerate(notes):
        n = int(sr * note_ms / 1000)
        start = i * n
        for j in range(n):
            t = j / sr
            # simple sine + 2nd harmonic for warmth, exponential decay envelope
            env = math.exp(-3.2 * t / (note_ms / 1000))
            sample = 0.6 * env * math.sin(2 * math.pi * freq * t)
            sample += 0.15 * env * math.sin(4 * math.pi * freq * t)
            # tiny attack click removal
            attack = min(1.0, (start + j) / (sr * 0.005))
            sample *= attack
            frames += struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def _ensure_chime() -> Path | None:
    """Return the path to the success chime WAV, synthesising it if needed."""
    p = _SOUNDS_DIR / "success.wav"
    if not p.exists():
        try:
            _synth_chime(p)
        except Exception:
            return None
    return p if p.exists() else None


def play_success() -> None:
    """Play the success chime. Silently no-ops if audio is unavailable."""
    path = _ensure_chime()
    if path is None:
        return
    try:
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is None:
            return
        snd = QSoundEffect()
        snd.setSource(QUrl.fromLocalFile(str(path)))
        snd.setVolume(0.7)
        snd.play()
        # keep a reference so it isn't GC'd before finishing
        play_success._last = snd  # type: ignore[attr-defined]
    except Exception:
        # audio is best-effort; never crash a conversion-finish handler
        pass
