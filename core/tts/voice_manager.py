"""V4.5.0: Reference voice manager for NeuTTS voice cloning.

Manages reference voice pairs (``<name>.wav`` + ``<name>.txt``) in a local
folder. Ships with preset voices and supports user-added voices for full
cloning power.

Folder structure::

    config/tts_voices/
      dave.wav          ← preset (shipped, can be replaced)
      dave.txt
      alex.wav          ← preset
      alex.txt
      my_voice.wav      ← user-added via UI
      my_voice.txt
      README.md

Each voice is identified by its name (filename without extension). The
``.txt`` file contains the exact transcript of the ``.wav`` file — this is
what NeuTTS uses to align the reference for cloning.

Users add voices via the Settings → TTS → Voices UI: pick a wav file,
type the transcript, give it a name. The pair is saved to the folder and
immediately available in the voice dropdown.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.tts.engine import LogFn

# Where reference voices are stored.
# V0.6.63: fixes the off-by-one parents[3] anchor (it resolved one level
# ABOVE the repo — the intended config/tts_voices was never found); frozen
# installs keep voices in user data (the bundled config/ is read-only).

logger = logging.getLogger(__name__)

from app_paths import is_frozen, resource_path  # late: anchor-local
from utils.settings import user_data_dir  # late: the user-data choke point

if is_frozen():
    _VOICES_DIR = user_data_dir() / "tts_voices"
else:
    _VOICES_DIR = resource_path("config", "tts_voices")


# Preset voices shipped with the app. Each entry is (name, description).
# The actual wav+txt files must exist in _VOICES_DIR; if they don't, we
# create placeholder txt files (the user must supply the wav).
_PRESET_VOICES = [
    ("dave", "Male — warm, clear (NeuTTS sample)"),
    ("jo", "Female — friendly, natural (NeuTTS sample)"),
    ("greta", "Female — authoritative (NeuTTS sample)"),
    ("juliette", "Female — soft, gentle (NeuTTS sample)"),
    ("mateo", "Male — energetic (NeuTTS sample)"),
]


class VoiceManager:
    """Manages reference voice pairs for NeuTTS voice cloning.

    Voices live in ``config/tts_voices/``. Each voice is a ``.wav`` + ``.txt``
    pair with the same base name. The manager lists available voices, adds
    user-supplied voices, and resolves a voice name to its (wav_path, text)
    pair.
    """

    def __init__(
        self,
        voices_dir: Path | None = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self.voices_dir = Path(voices_dir) if voices_dir else _VOICES_DIR
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._ensure_presets()

    def _ensure_presets(self) -> None:
        """Ensure preset voice files exist.

        V4.7.20: Copies both 'dave' and 'jo' preset voices from the NeuTTS
        project's samples/ folder if available.
        """
        readme = self.voices_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Reference Voices for NeuTTS\n\n"
                "Each voice is a `.wav` + `.txt` pair with the same name.\n"
                "The `.txt` file contains the exact transcript of the `.wav`.\n\n"
                "## Preset Voices\n"
                "- **dave** — Male, warm, clear (from NeuTTS samples)\n"
                "- **jo** — Female, friendly, natural (from NeuTTS samples)\n\n"
                "## Adding Your Own Voices\n"
                "Use Settings → TTS → Voices → 'Add voice':\n"
                "1. Pick a 3-15 second WAV of someone speaking\n"
                "2. Type exactly what they say (the transcript)\n"
                "3. Give it a name\n\n"
                "The voice appears in the dropdown immediately.\n",
                encoding="utf-8",
            )

        # V4.7.20: Copy all preset voices from the NeuTTS project
        for name, _desc in _PRESET_VOICES:
            wav = self.voices_dir / f"{name}.wav"
            txt = self.voices_dir / f"{name}.txt"
            if not wav.exists():
                self._try_copy_voice_from_neutts(name, wav, txt)

    def _try_copy_voice_from_neutts(self, name: str, dest_wav: Path, dest_txt: Path) -> None:
        """If the NeuTTS-Air project is installed, copy a preset voice."""
        from utils.settings import Settings

        s = Settings()
        neutts_path = Path(
            s.get(
                "tts.neutts_project_path",
                r"G:\Program Files\neutts-air",
            )
        )
        src_wav = neutts_path / "samples" / f"{name}.wav"
        src_txt = neutts_path / "samples" / f"{name}.txt"
        try:
            if src_wav.exists():
                shutil.copy2(src_wav, dest_wav)
                self.log(f"  ✅ Copied preset voice '{name}' from NeuTTS project", "DEBUG")
            if src_txt.exists():
                shutil.copy2(src_txt, dest_txt)
            elif not dest_txt.exists() and dest_wav.exists():
                dest_txt.write_text(
                    "This is a reference voice sample.",
                    encoding="utf-8",
                )
        except Exception as e:
            self.log(f"  ⚠️ Could not copy voice '{name}': {e}", "DEBUG")

    def list_voices(self) -> list[dict[str, str]]:
        """Return all available voices as a list of dicts.

        Each dict: ``{"name": str, "description": str, "has_wav": bool,
        "has_txt": bool, "wav_path": str, "txt_path": str}``.
        """
        voices = []
        seen_names = set()

        # Preset voices first (preserves order)
        for name, desc in _PRESET_VOICES:
            wav = self.voices_dir / f"{name}.wav"
            txt = self.voices_dir / f"{name}.txt"
            voices.append(
                {
                    "name": name,
                    "description": desc,
                    "has_wav": wav.exists(),
                    "has_txt": txt.exists(),
                    "wav_path": str(wav),
                    "txt_path": str(txt),
                }
            )
            seen_names.add(name)

        # User-added voices (any other wav+txt pairs in the folder)
        for wav_path in sorted(self.voices_dir.glob("*.wav")):
            name = wav_path.stem
            if name in seen_names:
                continue
            txt_path = self.voices_dir / f"{name}.txt"
            voices.append(
                {
                    "name": name,
                    "description": "User-added voice",
                    "has_wav": True,
                    "has_txt": txt_path.exists(),
                    "wav_path": str(wav_path),
                    "txt_path": str(txt_path),
                }
            )
            seen_names.add(name)

        return voices

    def get_voice(self, name: str) -> tuple[str | None, str]:
        """Resolve a voice name to (wav_path, transcript_text).

        Returns (None, "") if the voice doesn't exist or has no wav.
        """
        wav_path = self.voices_dir / f"{name}.wav"
        txt_path = self.voices_dir / f"{name}.txt"
        if not wav_path.exists():
            return (None, "")
        ref_text = ""
        if txt_path.exists():
            ref_text = txt_path.read_text(encoding="utf-8").strip()
        if not ref_text:
            # Fallback transcript — better than empty
            ref_text = "This is a reference voice sample."
        return (str(wav_path), ref_text)

    def add_voice(
        self,
        name: str,
        wav_source: Path,
        transcript: str,
    ) -> Path:
        """Add a new reference voice.

        Copies the wav to ``voices_dir/<name>.wav`` and writes the transcript
        to ``<name>.txt``. Sanitizes the name (alphanumeric + underscore).

        Returns the path to the saved wav. Raises on invalid input.
        """
        import re

        # Sanitize name: keep alphanumeric + underscore, lowercase
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip()).lower()
        if not clean_name:
            raise ValueError("Voice name cannot be empty")
        if len(clean_name) > 40:
            clean_name = clean_name[:40]

        wav_dest = self.voices_dir / f"{clean_name}.wav"
        txt_dest = self.voices_dir / f"{clean_name}.txt"

        # Copy the wav
        shutil.copy2(wav_source, wav_dest)

        # Write the transcript
        txt_dest.write_text(transcript.strip(), encoding="utf-8")

        self.log(f"  ✅ Added reference voice '{clean_name}'", "INFO")
        return wav_dest

    def remove_voice(self, name: str) -> bool:
        """Remove a reference voice (deletes both wav + txt).

        Returns True if deleted, False if not found. Preset voices can be
        removed too (the user can re-copy them by re-adding).
        """
        wav = self.voices_dir / f"{name}.wav"
        txt = self.voices_dir / f"{name}.txt"
        deleted = False
        if wav.exists():
            wav.unlink()
            deleted = True
        if txt.exists():
            txt.unlink()
            deleted = True
        if deleted:
            self.log(f"  🗑️ Removed reference voice '{name}'", "INFO")
        return deleted

    def voice_exists(self, name: str) -> bool:
        """Check if a voice (with wav) exists."""
        return (self.voices_dir / f"{name}.wav").exists()
