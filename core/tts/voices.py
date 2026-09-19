"""V4.2.0: Text-to-Speech voice catalogs + download/cache helpers.

Two catalogs:

* :data:`KOKORO_VOICES` — the 50+ preset voices shipped with Kokoro v1.0.
  Each entry is ``(voice_id, language, gender, descriptor)`` so the UI can
  group them (American Female, British Male, …) and show a human label.
* :data:`PIPER_FA_VOICES` — the three known Persian Piper voices (amir,
  mana, gyro) with their HuggingFace download coordinates.

The :func:`ensure_piper_voice` helper downloads a Piper voice's ``.onnx`` +
``.onnx.json`` pair into a local folder (defaulting to a ``voices/``
subfolder next to the piper binary) so the binary can load them with
``--model <name>.onnx``. Kokoro voices are bundled in the model repo and
need no separate download.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

# V0.13 (Phase 0): huggingface_hub is an OPTIONAL TTS-stack dependency (Piper
# voice downloads). Its former module-level import made the whole
# core.outputs → core.tts → controller chain crash on fresh installs; it is
# now imported lazily at the only call site that needs it.

# ── Kokoro voice catalog ───────────────────────────────────────────────────
# Voice IDs follow Kokoro's convention: <lang><gender>_<name>
#   a = American English, b = British English
#   f = female, m = male
# Descriptors are approximate, drawn from the Kokoro community's character notes.
# fmt: off

logger = logging.getLogger(__name__)

KOKORO_VOICES: list[tuple[str, str, str, str]] = [
    # American English — Female
    ("af_heart",     "en-US", "Female", "warm, empathetic"),
    ("af_bella",     "en-US", "Female", "soft, friendly"),
    ("af_nicole",    "en-US", "Female", "clear, professional"),
    ("af_sarah",     "en-US", "Female", "calm, narrative"),
    ("af_sky",       "en-US", "Female", "bright, upbeat"),
    # American English — Male
    ("am_michael",   "en-US", "Male",   "deep, authoritative"),
    ("am_adam",      "en-US", "Male",   "warm, conversational"),
    ("am_eric",      "en-US", "Male",   "neutral, news"),
    # British English — Female / Male
    ("bf_alice",     "en-GB", "Female", "posh, narrative"),
    ("bf_emma",      "en-GB", "Female", "warm, conversational"),
    ("bf_isabella",  "en-GB", "Female", "bright, young"),
    ("bf_lily",      "en-GB", "Female", "soft, gentle"),
    ("bm_george",    "en-GB", "Male",   "deep, formal"),
    ("bm_daniel",    "en-GB", "Male",   "warm, documentary"),
    ("bm_fable",    "en-GB", "Male",   "storyteller, rich"),
    ("bm_lewis",     "en-GB", "Male",   "neutral, clear"),
]
# fmt: on

# Default Kokoro voices (one female, one male) for the 2-host podcast.
KOKORO_DEFAULT_HOST_A = "af_heart"
KOKORO_DEFAULT_HOST_B = "am_michael"


def kokoro_voice_groups() -> list[tuple[str, list[tuple[str, str, str, str]]]]:
    """Group Kokoro voices by ``<Region> <Gender>`` for UI combo grouping.

    Returns ``[(group_label, [(voice_id, lang, gender, descriptor), …]), …]``.
    """
    groups: dict = {}
    order: list[str] = []
    for vid, lang, gender, desc in KOKORO_VOICES:
        region = "American" if lang.startswith("en-US") else "British"
        key = f"{region} {gender}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((vid, lang, gender, desc))
    return [(k, groups[k]) for k in order]


def kokoro_voice_label(voice_id: str) -> str:
    """Return a human-readable label for a Kokoro voice id."""
    for vid, _lang, _gender, desc in KOKORO_VOICES:
        if vid == voice_id:
            return f"{vid} — {desc}"
    return voice_id


# ── Piper Persian voice catalog ────────────────────────────────────────────
# Each entry: (voice_id, repo_id, subpath)
#   voice_id  → the file basename the binary expects, e.g. "fa_IR-amir-medium"
#   repo_id   → HuggingFace repo
#   subpath   → path inside the repo (without extension)
PIPER_FA_VOICES: list[tuple[str, str, str]] = [
    ("fa_IR-amir-medium", "rhasspy/piper-voices", "fa/fa_IR/amir/medium/fa_IR-amir-medium"),
    ("fa_IR-mana-medium", "MahtaFetrat/Mana-Persian-Piper", "fa_IR-mana-medium"),
    ("fa_IR-gyro-medium", "rhasspy/piper-voices", "fa/fa_IR/gyro/medium/fa_IR-gyro-medium"),
]

# User-confirmed best Persian voice (V4.2.0).
PIPER_FA_DEFAULT = "fa_IR-amir-medium"


def piper_voice_label(voice_id: str) -> str:
    """Return a human-readable label for a Piper Persian voice id."""
    _labels = {
        "fa_IR-amir-medium": "amir — male, rhasspy official",
        "fa_IR-mana-medium": "mana — trained on Mana-TTS dataset",
        "fa_IR-gyro-medium": "gyro — Microsoft Edge 'Farid' voice",
    }
    return _labels.get(voice_id, voice_id)


def piper_voice_repo(voice_id: str) -> tuple[str, str] | None:
    """Return ``(repo_id, subpath)`` for a Piper voice id, or None."""
    for vid, repo, sub in PIPER_FA_VOICES:
        if vid == voice_id:
            return (repo, sub)
    return None


def ensure_piper_voice(
    voice_id: str,
    voices_dir: Path,
    log_callback: callable | None = None,
) -> tuple[Path, Path]:
    """Ensure a Piper voice's .onnx + .onnx.json exist in ``voices_dir``.

    Downloads from HuggingFace on first use, then returns the local paths.
    Files are named ``<voice_id>.onnx`` and ``<voice_id>.onnx.json`` so the
    piper binary can load them with ``--model <voices_dir>/<voice_id>.onnx``.

    Returns ``(onnx_path, json_path)``. Raises on download failure.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    info = piper_voice_repo(voice_id)
    if info is None:
        raise ValueError(f"Unknown Piper voice: {voice_id}")
    repo_id, subpath = info

    voices_dir = Path(voices_dir)
    voices_dir.mkdir(parents=True, exist_ok=True)
    onnx_dst = voices_dir / f"{voice_id}.onnx"
    json_dst = voices_dir / f"{voice_id}.onnx.json"

    if onnx_dst.exists() and json_dst.exists():
        log(f"  ♻️  Piper voice cached: {voice_id}", "DEBUG")
        return (onnx_dst, json_dst)

    log(f"  ⬇️  Downloading Piper voice: {voice_id} (~60 MB)…", "INFO")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        raise ImportError(
            "huggingface_hub is required to download Piper voices — "
            "install with: pip install huggingface_hub (or the '[tts]' extra)"
        ) from e
    onnx_src = hf_hub_download(repo_id=repo_id, filename=f"{subpath}.onnx")
    json_src = hf_hub_download(repo_id=repo_id, filename=f"{subpath}.onnx.json")
    shutil.copy2(onnx_src, onnx_dst)
    shutil.copy2(json_src, json_dst)
    log(f"  ✅ Piper voice ready: {voice_id}", "INFO")
    return (onnx_dst, json_dst)
