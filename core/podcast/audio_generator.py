"""V11.37.0: Podcast audio generator using TTS tool settings.

Uses the persistent engine cache so models load ONCE and stay in VRAM.
- English: NeuTTS (primary) + Kokoro (fallback)
- Farsi: Sherpa Persian (primary) + Piper (fallback)

Generates per-line audio, then stitches with 150ms silence between lines.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from core.podcast.cancel_token import CancelToken
from core.podcast.script_generator import ScriptLine, ScriptResult
from core.tts.engine import LogFn

logger = logging.getLogger(__name__)

SILENCE_MS = 150  # silence between same-host lines
SAMPLE_RATE = 24000

# V11.63.0/V11.65.0: Conversational overlap settings
# V11.65.0: reduced max overlap from 800ms to 300ms — large overlaps
# caused audio distortion on VibeVoice.
OVERLAP_MIN_MS = 0  # sometimes immediate (interruption)
OVERLAP_MAX_MS = 300  # max overlap (gentle, won't distort)


def _crossfade_overlap(prev_audio, next_audio, overlap_samples):
    """V11.63.0: Overlap the end of prev_audio with the start of next_audio.

    Uses a linear crossfade: prev fades out while next fades in over the
    overlap region. Returns the combined audio.

    If overlap_samples is 0, just concatenates (immediate transition).
    """
    if overlap_samples <= 0:
        return np.concatenate([prev_audio, next_audio])

    # Ensure we have enough audio to overlap
    overlap_samples = min(overlap_samples, len(prev_audio), len(next_audio))
    if overlap_samples <= 0:
        return np.concatenate([prev_audio, next_audio])

    # Linear fade out for prev, fade in for next
    fade_out = np.linspace(1.0, 0.0, overlap_samples, dtype=prev_audio.dtype)
    fade_in = np.linspace(0.0, 1.0, overlap_samples, dtype=next_audio.dtype)

    # Split
    prev_tail = prev_audio[-overlap_samples:]
    prev_head = prev_audio[:-overlap_samples]
    next_tail = next_audio[overlap_samples:]
    next_head = next_audio[:overlap_samples]

    # Mix the overlap region
    if prev_tail.ndim == 1 and next_head.ndim == 1:
        mixed = prev_tail * fade_out + next_head * fade_in
    else:
        # Multi-channel (shouldn't happen, but handle it)
        mixed = prev_tail * fade_out[:, None] + next_head * fade_in[:, None]

    return np.concatenate([prev_head, mixed, next_tail])


def _detect_language(text: str) -> str:
    """Detect if text is Farsi or English.

    V0.6.0 (A1): delegates to the canonical ``core.tts.engine.detect_language``
    — the local copy this replaced matched only the base Arabic block and
    silently missed the presentation-form blocks (U+FB50–U+FDFF /
    U+FE70–U+FEFF), so Persian text extracted in presentation forms routed
    to the English engine branch.
    """
    from core.tts.engine import detect_language

    return detect_language(text)


def _log_vibevoice_config(vv_path: str, vv_voices: str, log: LogFn) -> None:
    """V0.6.15: log the VibeVoice config TRUTH (path + existence) before the
    subprocess spawn — when a podcast fails at the VibeVoice step the
    operator's report must show whether the paths were valid without a
    second round-trip."""
    _vv_path_ok = bool(vv_path) and Path(vv_path).exists()
    _vv_voices_ok = bool(vv_voices) and Path(vv_voices).is_dir()
    log(
        f"  🎙️ VibeVoice model: {vv_path or '(not set)'}"
        f"{' — OK' if _vv_path_ok else ' — NOT FOUND' if vv_path else ''}",
        "INFO",
    )
    log(
        f"  🎙️ VibeVoice voices dir: {vv_voices or '(not set)'}"
        f"{' — OK' if _vv_voices_ok else ' — NOT FOUND' if vv_voices else ''}",
        "INFO",
    )


def _synthesize_line(
    line: ScriptLine,
    out_path: Path,
    voice: str,
    settings,
    log: LogFn,
) -> Path | None:
    """Synthesize one script line to a WAV file.

    V11.40.0: simplified — Kokoro (fast), VibeVoice (quality), Sherpa (Farsi).
    Removed Qwen3-TTS, NeuTTS, Piper, Coqui, Persian VITS.
    """
    lang = _detect_language(line.text)

    try:
        if voice and voice.startswith("vibevoice:"):
            # V11.56.0: NO silent fallback to Kokoro. The podcast must
            # either succeed with the chosen voices or fail with a clear
            # error. Silently switching engines mid-podcast creates a
            # jarring voice change (Host A suddenly sounds completely
            # different).
            voice_name = voice[len("vibevoice:") :]
            vv_path = settings.get("tts.vibevoice_model_path", "")
            vv_voices = settings.get("tts.vibevoice_voices_dir", "")
            _log_vibevoice_config(vv_path, vv_voices, log)  # V0.6.15
            if not vv_path:
                log(
                    "  ❌ VibeVoice model path not set — cannot generate. "
                    "Set it in Settings → TTS → VibeVoice model path.",
                    "ERROR",
                )
                return None
            try:
                from core.tts.engine_cache import get_vibevoice_engine

                engine = get_vibevoice_engine(
                    model_path=vv_path,
                    voices_dir=vv_voices,
                    default_voice=voice_name,
                    log_callback=log,
                )
                result = engine.synthesize(line.text, out_path, voice_name, 1.0)
                if result and Path(result).exists() and Path(result).stat().st_size > 44:
                    return result
                log(
                    "  ❌ VibeVoice produced no output for this line. "
                    "Podcast will fail — no engine switching, no retry.",
                    "ERROR",
                )
                # V11.57.0: RAISE — don't return None.
                raise RuntimeError(
                    "VibeVoice produced no output. Podcast failed — no engine switching, no retry."
                )
            except Exception as ve:
                log(
                    f"  ❌ VibeVoice failed: {ve}. Podcast will fail — "
                    f"no engine switching, no retry.",
                    "ERROR",
                )
                # V11.57.0: RE-RAISE — don't return None. Returning None
                # lets the podcast continue to the next line, which tries
                # to restart VibeVoice → death spiral ("resetting").
                # The user's requirement: "either success or fail."
                raise

        elif lang == "fa":
            # V11.44.0: Farsi default: Kokoro
            from core.tts.engine_cache import get_kokoro_engine

            engine = get_kokoro_engine(log_callback=log)
            return engine.synthesize(line.text, out_path, voice or "af_heart", 1.0)

        else:
            # English default: Kokoro (fast)
            from core.tts.engine_cache import get_kokoro_engine

            engine = get_kokoro_engine(log_callback=log)
            return engine.synthesize(line.text, out_path, voice or "af_heart", 1.0)
    except RuntimeError as e:
        # V11.57.0: re-raise RuntimeError — these are intentional failures
        # (VibeVoice crash/timeout/error) that should STOP the podcast,
        # not be swallowed and skipped.
        log(f"  ❌ TTS failed (fatal): {e}", "ERROR")
        raise
    except Exception as e:
        log(f"  ⚠️ TTS failed for line: {e}", "WARNING")
        return None


def generate_podcast_audio(
    script: ScriptResult,
    out_path: Path,
    host_a_voice: str,
    host_b_voice: str,
    settings,
    log_callback: LogFn | None = None,
    progress_callback=None,
    cancel_token: CancelToken | None = None,
) -> Path | None:
    """Generate a podcast audio file from a script.

    V11.41.0: Handles vocal cues ([pause], [breath], [laugh], [hmm]) and
    adds conversational overlap between host transitions.

    V0.6.18 (W-d3): ``cancel_token`` — the line-by-line loop checks the
    token at the top of every iteration. The UI's cancel button calls
    ``token.cancel()`` from the main thread; the worker sees the flip on
    the next line and exits cleanly, releasing the temp WAVs and leaving
    the VibeVoice / Qwen subprocess alive-but-idle for the next run (the
    subprocess teardown contract is unchanged — only the line loop is
    new). The returned path is ``None`` on cancellation (no audio file
    is written); the caller logs "cancelled by user" via the token's
    ``reason``.

    Args:
        script: The ScriptResult from script_generator.
        out_path: Where to save the final stitched WAV.
        host_a_voice: Voice name/ID for Host A.
        host_b_voice: Voice name/ID for Host B (ignored in lecture mode).
        settings: Settings instance for TTS config.
        log_callback: Optional logging callback.
        progress_callback: Optional callback(pct: int, msg: str).
        cancel_token: Optional CancelToken; when its ``cancelled`` flag
            flips True, the loop exits at the next iteration boundary.

    Returns:
        Path to the output WAV, or None on failure / cancellation.
    """
    from core.podcast.script_generator import strip_vocal_cues

    log = log_callback or (lambda msg, level="INFO": None)
    total = len(script.lines)
    if total == 0:
        log("  ❌ No script lines to synthesize", "ERROR")
        return None

    log(f"  🎙️ Generating audio for {total} lines...", "INFO")

    # V11.51.0: log the CUDA/GPU status at the START so the user can
    # verify the podcast is using GPU (not CPU).
    try:
        import torch

        cuda_ok = torch.cuda.is_available()
        if cuda_ok:
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            log(f"  ✅ GPU detected: {gpu_name} ({vram} MB) — torch.cuda=True", "INFO")
        else:
            log("  ⚠️ NO GPU — torch.cuda=False. Podcast will be VERY slow on CPU.", "WARNING")
            log(f"     torch.version.cuda={getattr(torch.version, 'cuda', None)!r}", "WARNING")
    except Exception as e:
        log(f"  (GPU check skipped: {e})", "WARNING")

    chunk_paths: list[Path] = []
    chunk_cues: list[list] = []  # vocal cues per chunk
    chunk_hosts: list[str] = []  # which host for each chunk

    import time as _time

    audio_start = _time.time()

    with tempfile.TemporaryDirectory(prefix="podcast_") as tmp:
        for i, line in enumerate(script.lines):
            # V0.6.18 (W-d3): cancel check at the iteration boundary —
            # the line loop's only safe exit point. The token's flag is
            # thread-safe (Lock-guarded); the UI button calls .cancel()
            # from the main thread, the worker sees it on the NEXT line
            # (mid-line cancel would orphan a half-synthesized WAV, so
            # we wait for the boundary). On cancel we exit cleanly: the
            # temp WAVs are released by the surrounding TemporaryDirectory,
            # the TTS subprocess is left alive-but-idle, and we return
            # None — the caller's "success or fail" contract holds.
            if cancel_token is not None and cancel_token.cancelled:
                _reason = cancel_token.reason or "cancelled"
                log(
                    f"  ⏹️ Podcast generation cancelled at line {i}/{total} "
                    f"({_reason}). No audio file will be produced.",
                    "WARNING",
                )
                if progress_callback:
                    progress_callback(0, f"⏹️ Cancelled: {_reason}")
                return None

            # Determine which voice to use
            voice = host_a_voice if line.host == "A" else host_b_voice

            pct = int((i / total) * 100)
            line_start = _time.time()
            if progress_callback:
                progress_callback(pct, f"🎙️ Line {i + 1}/{total} (Host {line.host})")
            log(f"  🎙️ [{i + 1}/{total}] Host {line.host}: {line.text[:60]}...", "INFO")

            # V11.41.0: Strip vocal cues before TTS, save them for post-processing
            clean_text, cues = strip_vocal_cues(line.text)

            # Skip empty lines (just cues)
            if not clean_text.strip():
                # This line is ONLY a vocal cue (e.g., just "[pause]")
                # Insert silence directly
                if cues:
                    chunk_path = Path(tmp) / f"line_{i:04d}.wav"
                    total_silence = sum(c[2] for c in cues if c[2] > 0)
                    if total_silence > 0:
                        silence_data = np.zeros(int(SAMPLE_RATE * total_silence), dtype=np.float32)
                        sf.write(str(chunk_path), silence_data, SAMPLE_RATE)
                        chunk_paths.append(chunk_path)
                        chunk_cues.append([])
                        chunk_hosts.append(line.host)
                continue

            # Create a modified line with clean text for TTS
            from core.podcast.script_generator import ScriptLine

            clean_line = ScriptLine(
                host=line.host,
                text=clean_text,
                source_ref=line.source_ref,
                segment_type=line.segment_type,
            )

            chunk_path = Path(tmp) / f"line_{i:04d}.wav"
            try:
                result = _synthesize_line(clean_line, chunk_path, voice, settings, log)
            except RuntimeError as e:
                # V11.57.0: VibeVoice (or Kokoro) had a fatal error.
                # STOP the podcast — no retry, no engine switch.
                # The user's requirement: "either success or fail."
                log(f"  ❌ [{i + 1}/{total}] FATAL: {e}", "ERROR")
                log(f"  ❌ Podcast generation STOPPED at line {i + 1}.", "ERROR")
                log("  ❌ No audio file will be produced.", "ERROR")
                return None
            line_time = _time.time() - line_start
            if result and Path(result).exists():
                chunk_paths.append(Path(result))
                chunk_cues.append(cues)
                chunk_hosts.append(line.host)
                # V11.51.0: log per-line timing + audio duration
                try:
                    import soundfile as _sf

                    _data, _sr = _sf.read(str(result))
                    _dur = len(_data) / _sr
                    elapsed_total = _time.time() - audio_start
                    log(
                        f"  ✅ [{i + 1}/{total}] done in {line_time:.1f}s "
                        f"(audio: {_dur:.1f}s, total elapsed: {elapsed_total:.0f}s)",
                        "INFO",
                    )
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
                    log(f"  ✅ [{i + 1}/{total}] done in {line_time:.1f}s", "INFO")
            else:
                log(f"  ⚠️ Skipping line {i + 1} (TTS failed in {line_time:.1f}s)", "WARNING")

        if not chunk_paths:
            log("  ❌ No audio chunks produced — ALL lines failed TTS", "ERROR")
            log(f"  ❌ Total lines attempted: {total}, succeeded: 0", "ERROR")
            log(f"  ❌ Host A voice: '{host_a_voice}', Host B voice: '{host_b_voice}'", "ERROR")
            log(
                "  ❌ Check that TTS is configured (Settings → TTS) and the voice names are valid",
                "ERROR",
            )
            return None

        # V11.41.0/V11.63.0: Stitch with conversational overlap + crossfade
        if progress_callback:
            progress_callback(95, "🔗 Stitching audio with natural overlap...")
        log(
            f"  🔗 Stitching {len(chunk_paths)} audio chunks with conversational overlap...", "INFO"
        )

        audio_parts = []
        for cp in chunk_paths:
            data, sr = sf.read(str(cp))
            audio_parts.append(data)

        # V11.63.0: New stitching approach — overlap + crossfade for
        # host transitions, silence for same-host, backchannel mixing.
        import random as _rng

        rng = _rng.Random(42)  # deterministic

        # Process each chunk: apply cues only (V11.65.0: reverted mic
        # variation + exclamation boost — they caused severe distortion
        # on VibeVoice, making it sound like a "ghoul/mountain troll").
        processed_parts = []
        for i, (part, cues, host) in enumerate(
            zip(audio_parts, chunk_cues, chunk_hosts, strict=False)
        ):
            # Apply vocal cue silences WITHIN the part
            SILENCE_CUE_TYPES = (
                "pause",
                "breath",
                "sigh",
                "chuckle",
                "gasp",
                "throat_clear",
            )
            part_with_cues = part
            for _cue_pos, cue_type, cue_duration in cues:
                if cue_type in SILENCE_CUE_TYPES and cue_duration > 0:
                    cue_silence = np.zeros(int(SAMPLE_RATE * cue_duration), dtype=part.dtype)
                    part_with_cues = np.concatenate([part_with_cues, cue_silence])
                    log(f"  🎭 Inserted {cue_type} ({cue_duration}s) in line {i + 1}", "DEBUG")

            processed_parts.append((part_with_cues, host))

        # Now stitch with overlap/crossfade
        if not processed_parts:
            final_audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        else:
            final_audio = processed_parts[0][0]
            for i in range(1, len(processed_parts)):
                prev_part, prev_host = processed_parts[i - 1]
                curr_part, curr_host = processed_parts[i]

                if prev_host != curr_host:
                    # V11.63.0: Host transition — OVERLAP instead of silence
                    # Variable overlap: sometimes 0 (immediate), sometimes
                    # up to 800ms (B starts during A's last words).
                    # This creates the natural "jumping in" feel.
                    overlap_ms = rng.randint(OVERLAP_MIN_MS, OVERLAP_MAX_MS)
                    overlap_samples = int(SAMPLE_RATE * overlap_ms / 1000)

                    if overlap_ms > 0:
                        log(
                            f"  🔀 Overlapping {prev_host}→{curr_host} ({overlap_ms}ms crossfade)",
                            "DEBUG",
                        )
                        final_audio = _crossfade_overlap(final_audio, curr_part, overlap_samples)
                    else:
                        # Immediate transition (interruption)
                        log(
                            f"  ⚡ Immediate transition {prev_host}→{curr_host} (interruption)",
                            "DEBUG",
                        )
                        final_audio = np.concatenate([final_audio, curr_part])
                else:
                    # Same host — small silence
                    silence = np.zeros(int(SAMPLE_RATE * SILENCE_MS / 1000), dtype=curr_part.dtype)
                    final_audio = np.concatenate([final_audio, silence, curr_part])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), final_audio, SAMPLE_RATE)

        if progress_callback:
            progress_callback(100, "✅ Podcast audio complete")
        log(f"  ✅ Podcast saved: {out_path} ({len(final_audio) / SAMPLE_RATE:.1f}s)", "INFO")
        return out_path
