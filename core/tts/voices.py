"""V4.2.0: Text-to-Speech voice catalogs + download/cache helpers.

One catalog:

* :data:`KOKORO_VOICES` — the 50+ preset voices shipped with Kokoro v1.0.
  Each entry is ``(voice_id, language, gender, descriptor)`` so the UI can
  group them (American Female, British Male, …) and show a human label.

V0.6.64: the Piper Persian voice catalog + its HuggingFace download
helper were REMOVED with the Piper engine (user decision, remaining-
surface item 4). Persian TTS no longer routes through this module —
Kokoro voices are bundled in the model repo and need no separate
download.
"""

from __future__ import annotations

import logging

# V0.13 (Phase 0): huggingface_hub is an OPTIONAL TTS-stack dependency (VibeVoice
# / Qwen3-TTS / Persian-VITS model downloads in their engine modules). Its
# former module-level import made the whole core.outputs → core.tts →
# controller chain crash on fresh installs; engine modules import it lazily
# at their only call sites that need it.

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


# V0.6.64: the Piper Persian voice catalog (PIPER_FA_VOICES / PIPER_FA_DEFAULT
# / piper_voice_label / piper_voice_repo / ensure_piper_voice) was REMOVED
# together with the Piper engine — the whole binary-subprocess Persian path
# is gone (user decision, remaining-surface item 4: "Remove piper entirely").
