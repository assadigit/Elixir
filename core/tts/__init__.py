"""V4.2.0 + V4.4.0 + V4.5.0 + V11.34.0: TTS engines, voice catalogs, normalizer, voice manager.

Public API:
    TTSEngine, KokoroEngine, PiperEngine, NeuTTSEngine, PersianVitsEngine, TTSRouter, detect_language
    KOKORO_VOICES, PIPER_FA_VOICES, ensure_piper_voice
    TextNormalizer, create_normalizer_from_settings (V4.4.0)
    VoiceManager (V4.5.0 — reference voice management for NeuTTS cloning)
    PersianVitsEngine (V11.34.0 — high-quality local Farsi TTS)
"""

import logging

from core.tts.engine import (
    KokoroEngine,
    PiperEngine,
    TTSEngine,
    TTSRouter,
    detect_language,
)
from core.tts.neutts_engine import NeuTTSEngine
from core.tts.normalizer import (
    TextNormalizer,
    create_normalizer_from_settings,
)
from core.tts.persian_vits_engine import PERSIAN_VITS_MODELS, PersianVitsEngine
from core.tts.qwen_tts_engine import QWEN_TTS_KNOWN_SPEAKERS, QwenTtsEngine
from core.tts.sherpa_persian_engine import SHERPA_PERSIAN_VOICES, SherpaPersianEngine
from core.tts.vibevoice_engine import VIBEVOICE_ENGLISH_VOICES, VibeVoiceEngine
from core.tts.voice_manager import VoiceManager
from core.tts.voices import (
    KOKORO_DEFAULT_HOST_A,
    KOKORO_DEFAULT_HOST_B,
    KOKORO_VOICES,
    PIPER_FA_DEFAULT,
    PIPER_FA_VOICES,
    ensure_piper_voice,
    kokoro_voice_groups,
    kokoro_voice_label,
    piper_voice_label,
)

logger = logging.getLogger(__name__)

__all__ = [
    "TTSEngine",
    "KokoroEngine",
    "PiperEngine",
    "NeuTTSEngine",
    "QwenTtsEngine",
    "QWEN_TTS_KNOWN_SPEAKERS",
    "VibeVoiceEngine",
    "VIBEVOICE_ENGLISH_VOICES",
    "PersianVitsEngine",
    "PERSIAN_VITS_MODELS",
    "SherpaPersianEngine",
    "SHERPA_PERSIAN_VOICES",
    "TTSRouter",
    "detect_language",
    "KOKORO_VOICES",
    "PIPER_FA_VOICES",
    "PIPER_FA_DEFAULT",
    "KOKORO_DEFAULT_HOST_A",
    "KOKORO_DEFAULT_HOST_B",
    "ensure_piper_voice",
    "kokoro_voice_groups",
    "kokoro_voice_label",
    "piper_voice_label",
    "TextNormalizer",
    "create_normalizer_from_settings",
    "VoiceManager",
]
