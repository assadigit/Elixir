"""V11.37.0: Persistent TTS engine cache.

Solves the "NeuTTS is slow" problem: the TTS dialog was creating a NEW
NeuTTSEngine on every click, which reloads the 765MB GGUF model from disk
each time (~30-60s overhead). This module keeps the engine alive in VRAM
for all subsequent calls.

Usage:
    from core.tts.engine_cache import get_neutts_engine, get_sherpa_engine
    engine = get_neutts_engine(log_callback=...)  # loads once, reuses
    engine.synthesize(text, out_path, voice, speed)
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.tts.engine import LogFn

logger = logging.getLogger(__name__)

# Singleton cache: engine_key → engine instance
_engines: dict[str, object] = {}


def get_neutts_engine(
    gguf_path: str,
    neutts_project_path: str,
    log_callback: LogFn | None = None,
) -> object:
    """Get or create a persistent NeuTTSEngine.

    The engine is cached by its GGUF path so different models don't
    collide. The model loads once and stays in VRAM until the app exits.
    """
    key = f"neutts:{gguf_path}"
    if key not in _engines:
        from core.tts.neutts_engine import NeuTTSEngine

        engine = NeuTTSEngine(
            gguf_path=Path(gguf_path),
            neutts_project_path=Path(neutts_project_path),
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info("NeuTTS engine cached (will reuse for subsequent calls)")
    else:
        logger.debug("NeuTTS engine reused from cache")
    return _engines[key]


def get_qwen_tts_engine(
    model_path: str,
    speaker: str = "Vivian",
    language: str = "English",
    log_callback: LogFn | None = None,
) -> object:
    """V11.38.0: Get or create a persistent QwenTtsEngine.

    Replaces NeuTTS as the primary English TTS engine.
    The model loads once and stays in VRAM.
    """
    key = f"qwen_tts:{model_path}"
    if key not in _engines:
        from core.tts.qwen_tts_engine import QwenTtsEngine

        engine = QwenTtsEngine(
            model_path=model_path,
            speaker=speaker,
            language=language,
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info("Qwen3-TTS engine cached (will reuse for subsequent calls)")
    else:
        logger.debug("Qwen3-TTS engine reused from cache")
    return _engines[key]


def get_sherpa_engine(
    voice_id: str,
    log_callback: LogFn | None = None,
) -> object:
    """Get or create a persistent SherpaPersianEngine."""
    key = f"sherpa:{voice_id}"
    if key not in _engines:
        from core.tts.sherpa_persian_engine import SherpaPersianEngine

        engine = SherpaPersianEngine(
            voice_id=voice_id,
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info(f"Sherpa engine cached for voice '{voice_id}'")
    else:
        logger.debug(f"Sherpa engine reused for voice '{voice_id}'")
    return _engines[key]


def get_vibevoice_engine(
    model_path: str,
    voices_dir: str = "",
    default_voice: str = "en-Carter_man",
    log_callback: LogFn | None = None,
) -> object:
    """V11.40.0: Get or create a persistent VibeVoiceEngine."""
    key = f"vibevoice:{model_path}"
    if key not in _engines:
        from core.tts.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine(
            model_path=model_path,
            voices_dir=voices_dir,
            default_voice=default_voice,
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info("VibeVoice engine cached (will reuse for subsequent calls)")
    else:
        logger.debug("VibeVoice engine reused from cache")
    return _engines[key]


def get_kokoro_engine(
    log_callback: LogFn | None = None,
) -> object:
    """Get or create a persistent KokoroEngine."""
    key = "kokoro"
    if key not in _engines:
        from core.tts.engine import KokoroEngine

        engine = KokoroEngine(
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info("Kokoro engine cached")
    return _engines[key]


def get_piper_engine(
    piper_binary: Path,
    piper_voices_dir: Path | None,
    log_callback: LogFn | None = None,
) -> object:
    """Get or create a persistent PiperEngine."""
    key = f"piper:{piper_binary}"
    if key not in _engines:
        from core.tts.engine import PiperEngine

        engine = PiperEngine(
            piper_binary,
            piper_voices_dir,
            log_callback=log_callback or (lambda msg, level="INFO": None),
        )
        _engines[key] = engine
        logger.info("Piper engine cached")
    return _engines[key]


def clear_cache() -> None:
    """Clear all cached engines (frees VRAM).

    V18.20.4.12 (W-c12): each cached engine is now GRACEFULLY torn down
    BEFORE its cache slot is dropped. The old body was a bare
    ``_engines.clear()`` — teardown was left to ``__del__`` at
    GC/interpreter-exit time, which is unreliable during module teardown
    (engine globals may already be gone) and kept the subprocesses + VRAM
    alive until then. Every engine in this package owns a never-raise
    teardown invoked from its own ``__del__`` (NeuTTSEngine.
    ``_cleanup_process``: quit JSON → wait(5) → kill; Qwen/VibeVoice/
    Sherpa ``_cleanup``: shared-base graceful quit → kill); we call the
    same hooks EAGERLY here. Public names (close/quit/stop/shutdown) are
    tried first so foreign engine objects (tests, future engines) are
    honoured too; the first hook found wins so an engine exposing several
    is never torn down twice. A stuck engine can NEVER raise past this
    function — per-engine failures are logged and the cache is cleared
    regardless.
    """
    for key, engine in list(_engines.items()):
        try:
            torn_down = False
            for name in ("close", "quit", "stop", "shutdown", "_cleanup_process", "_cleanup"):
                hook = getattr(engine, name, None)
                if callable(hook):
                    hook()
                    torn_down = True
                    break
            if not torn_down:
                logger.debug(
                    "cached engine %r (%s) exposes no teardown hook — dropping reference only",
                    key,
                    type(engine).__name__,
                )
        except Exception as e:
            logger.warning(
                "TTS engine cache: teardown of %r failed (%s: %s) — dropping the reference anyway",
                key,
                type(e).__name__,
                e,
            )
    _engines.clear()
    logger.info("TTS engine cache cleared")


def cached_engine_count() -> int:
    """Return the number of cached engines."""
    return len(_engines)
