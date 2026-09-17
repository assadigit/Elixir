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

from core.podcast.script_generator import ScriptLine, ScriptResult
from core.tts.engine import LogFn

logger = logging.getLogger(__name__)

SILENCE_MS = 150  # silence between same-host lines
SAMPLE_RATE = 24000

# V11.63.0/V11.65.0: Conversational overlap settings
# V11.65.0: reduced max overlap from 800ms to 300ms — large overlaps
# caused audio distortion on VibeVoice.
OVERLAP_MIN_MS = 0      # sometimes immediate (interruption)
OVERLAP_MAX_MS = 300    # max overlap (gentle, won't distort)
BACKCHANNEL_OVERLAP_MS = 600  # backchannel layered over last 0.6s
BACKCHANNEL_VOLUME = 0.35  # backchannel at 35% volume (background)


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


def _mix_backchannel(host_audio, backchannel_audio, offset_ms, volume):
    """V11.63.0: Layer a backchannel ('yeah', 'right') over host_audio.

    The backchannel is placed at offset_ms from the END of host_audio,
    at reduced volume, creating the "yeah yeah, you're right" effect
    while the other person is still speaking.
    """
    sr = SAMPLE_RATE
    offset_samples = int(sr * offset_ms / 1000)
    bc_len = len(backchannel_audio)

    # Where to insert (from the end)
    insert_pos = len(host_audio) - offset_samples
    if insert_pos < 0:
        insert_pos = 0

    # How much of the backchannel fits
    end_pos = min(insert_pos + bc_len, len(host_audio))
    actual_bc_len = end_pos - insert_pos

    if actual_bc_len <= 0:
        return host_audio

    # Mix: host audio stays at full volume, backchannel at reduced volume
    result = host_audio.copy()
    bc_segment = backchannel_audio[:actual_bc_len] * volume

    if result.ndim == 1 and bc_segment.ndim == 1:
        result[insert_pos:end_pos] = result[insert_pos:end_pos] + bc_segment
    else:
        result[insert_pos:end_pos] = result[insert_pos:end_pos] + bc_segment[:, None]

    # Prevent clipping
    max_val = np.max(np.abs(result))
    if max_val > 0.99:
        result = result * (0.99 / max_val)

    return result


def _apply_mic_variation(audio, rng, intensity=0.12):
    """V11.64.0: Apply subtle gain variation to simulate head movement.

    Podcasters move their head slightly toward/away from the mic, causing
    the volume to fluctuate. This applies a slow gain envelope (±intensity)
    to make the audio feel less static and more "live".

    The envelope is a combination of slow sine waves at different
    frequencies, ensuring the volume drifts naturally rather than
    predictably.

    Args:
        audio: numpy array of audio samples.
        rng: random.Random instance for deterministic variation.
        intensity: max gain change (0.12 = ±12% volume variation).
    """
    if len(audio) < SAMPLE_RATE // 2:  # skip very short clips (< 0.5s)
        return audio

    # Generate a slow envelope using multiple sine waves at different
    # frequencies — this creates a natural-sounding drift.
    t = np.arange(len(audio), dtype=np.float32) / SAMPLE_RATE
    # Random frequencies between 0.2-0.8 Hz (very slow, ~1-4s per cycle)
    freq1 = rng.uniform(0.2, 0.5)
    freq2 = rng.uniform(0.3, 0.8)
    freq3 = rng.uniform(0.1, 0.3)
    # Random phase offsets
    phase1 = rng.uniform(0, 2 * np.pi)
    phase2 = rng.uniform(0, 2 * np.pi)
    phase3 = rng.uniform(0, 2 * np.pi)

    # Combine three sine waves for a natural envelope
    envelope = (
        0.5 * np.sin(2 * np.pi * freq1 * t + phase1) +
        0.3 * np.sin(2 * np.pi * freq2 * t + phase2) +
        0.2 * np.sin(2 * np.pi * freq3 * t + phase3)
    ) * intensity

    # Center around 1.0 (no net volume change)
    gain = 1.0 + envelope

    # Apply the gain
    result = audio * gain[:, None] if audio.ndim > 1 else audio * gain

    # Normalize to prevent clipping
    max_val = np.max(np.abs(result))
    if max_val > 0.99:
        result = result * (0.99 / max_val)

    return result


def _boost_exclamations(audio, text, rng):
    """V11.64.0: Boost volume on exclamatory sentences.

    If the text contains exclamation marks (!), "wow", "what", "awesome",
    "kidding", etc., we boost the volume of the last portion of the audio
    to emphasize the excitement. This makes "wooow!" and "that's AWESOME!"
    sound more energetic.

    Args:
        audio: numpy array of audio samples.
        text: the original text (to detect exclamations).
        rng: random.Random instance.
    """
    # Detect exclamatory content
    exclamation_words = (
        "wow", "wooow", "whattt", "what", "awesome", "awww",
        "kidding", "no way", "oh my", "incredible", "amazing",
        "insane", "crazy", "mind-blowing", "unbelievable",
    )
    text_lower = text.lower()
    has_exclamation = (
        "!" in text or
        any(w in text_lower for w in exclamation_words) or
        text.isupper()  # ALL CAPS = shouting
    )

    if not has_exclamation or len(audio) < SAMPLE_RATE:
        return audio

    # Boost the last 30-50% of the audio (where the exclamation usually is)
    boost_start = rng.uniform(0.5, 0.7)  # start from 50-70% into the audio
    boost_factor = rng.uniform(1.15, 1.30)  # 15-30% volume boost

    start_sample = int(len(audio) * boost_start)
    result = audio.copy()

    # Apply a smooth ramp-up to the boost (avoid sudden jumps)
    ramp_len = min(int(SAMPLE_RATE * 0.1), len(audio) - start_sample)  # 100ms ramp
    if ramp_len > 0:
        ramp = np.linspace(1.0, boost_factor, ramp_len, dtype=audio.dtype)
        if result.ndim > 1:
            result[start_sample:start_sample + ramp_len] *= ramp[:, None]
            result[start_sample + ramp_len:] *= boost_factor
        else:
            result[start_sample:start_sample + ramp_len] *= ramp
            result[start_sample + ramp_len:] *= boost_factor

    # Normalize to prevent clipping
    max_val = np.max(np.abs(result))
    if max_val > 0.99:
        result = result * (0.99 / max_val)

    return result


def _detect_language(text: str) -> str:
    """Detect if text is Farsi or English."""
    import re
    arabic_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F]', text))
    non_space = max(len([c for c in text if not c.isspace()]), 1)
    if arabic_chars / non_space > 0.2:
        return "fa"
    return "en"


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
            voice_name = voice[len("vibevoice:"):]
            vv_path = settings.get("tts.vibevoice_model_path", "")
            vv_voices = settings.get("tts.vibevoice_voices_dir", "")
            if not vv_path:
                log("  ❌ VibeVoice model path not set — cannot generate. "
                    "Set it in Settings → TTS → VibeVoice model path.",
                    "ERROR")
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
                log("  ❌ VibeVoice produced no output for this line. "
                    "Podcast will fail — no engine switching, no retry.",
                    "ERROR")
                # V11.57.0: RAISE — don't return None.
                raise RuntimeError(
                    "VibeVoice produced no output. Podcast failed — "
                    "no engine switching, no retry.")
            except Exception as ve:
                log(f"  ❌ VibeVoice failed: {ve}. Podcast will fail — "
                    f"no engine switching, no retry.", "ERROR")
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
) -> Path | None:
    """Generate a podcast audio file from a script.

    V11.41.0: Handles vocal cues ([pause], [breath], [laugh], [hmm]) and
    adds conversational overlap between host transitions.

    Args:
        script: The ScriptResult from script_generator.
        out_path: Where to save the final stitched WAV.
        host_a_voice: Voice name/ID for Host A.
        host_b_voice: Voice name/ID for Host B (ignored in lecture mode).
        settings: Settings instance for TTS config.
        log_callback: Optional logging callback.
        progress_callback: Optional callback(pct: int, msg: str).

    Returns:
        Path to the output WAV, or None on failure.
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
            # Determine which voice to use
            voice = host_a_voice if line.host == "A" else host_b_voice

            pct = int((i / total) * 100)
            line_start = _time.time()
            if progress_callback:
                progress_callback(pct, f"🎙️ Line {i+1}/{total} (Host {line.host})")
            log(f"  🎙️ [{i+1}/{total}] Host {line.host}: {line.text[:60]}...", "INFO")

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
                log(f"  ❌ [{i+1}/{total}] FATAL: {e}", "ERROR")
                log(f"  ❌ Podcast generation STOPPED at line {i+1}.", "ERROR")
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
                    log(f"  ✅ [{i+1}/{total}] done in {line_time:.1f}s "
                        f"(audio: {_dur:.1f}s, total elapsed: {elapsed_total:.0f}s)",
                        "INFO")
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
                    log(f"  ✅ [{i+1}/{total}] done in {line_time:.1f}s", "INFO")
            else:
                log(f"  ⚠️ Skipping line {i+1} (TTS failed in {line_time:.1f}s)", "WARNING")

        if not chunk_paths:
            log("  ❌ No audio chunks produced — ALL lines failed TTS", "ERROR")
            log(f"  ❌ Total lines attempted: {total}, succeeded: 0", "ERROR")
            log(f"  ❌ Host A voice: '{host_a_voice}', Host B voice: '{host_b_voice}'", "ERROR")
            log("  ❌ Check that TTS is configured (Settings → TTS) and the voice names are valid", "ERROR")
            return None

        # V11.41.0/V11.63.0: Stitch with conversational overlap + crossfade
        if progress_callback:
            progress_callback(95, "🔗 Stitching audio with natural overlap...")
        log(f"  🔗 Stitching {len(chunk_paths)} audio chunks with "
            f"conversational overlap...", "INFO")

        audio_parts = []
        for cp in chunk_paths:
            data, sr = sf.read(str(cp))
            audio_parts.append(data)

        # V11.63.0: New stitching approach — overlap + crossfade for
        # host transitions, silence for same-host, backchannel mixing.
        import random as _rng
        rng = _rng.Random(42)  # deterministic

        # Load backchannel audio snippets (generate them if needed)
        backchannel_snippets = {}
        backchannel_texts = {"yeah": "Yeah.", "right": "Right.",
                            "mhm": "Mhm.", "exactly": "Exactly."}

        # Process each chunk: apply cues only (V11.65.0: reverted mic
        # variation + exclamation boost — they caused severe distortion
        # on VibeVoice, making it sound like a "ghoul/mountain troll").
        processed_parts = []
        for i, (part, cues, host) in enumerate(
            zip(audio_parts, chunk_cues, chunk_hosts)
        ):
            # Apply vocal cue silences WITHIN the part
            SILENCE_CUE_TYPES = (
                "pause", "breath", "sigh", "chuckle",
                "gasp", "throat_clear",
            )
            part_with_cues = part
            for cue_pos, cue_type, cue_duration in cues:
                if cue_type in SILENCE_CUE_TYPES and cue_duration > 0:
                    cue_silence = np.zeros(
                        int(SAMPLE_RATE * cue_duration), dtype=part.dtype)
                    part_with_cues = np.concatenate(
                        [part_with_cues, cue_silence])
                    log(f"  🎭 Inserted {cue_type} ({cue_duration}s) "
                        f"in line {i+1}", "DEBUG")

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
                        log(f"  🔀 Overlapping {prev_host}→{curr_host} "
                            f"({overlap_ms}ms crossfade)", "DEBUG")
                        final_audio = _crossfade_overlap(
                            final_audio, curr_part, overlap_samples)
                    else:
                        # Immediate transition (interruption)
                        log(f"  ⚡ Immediate transition {prev_host}→{curr_host} "
                            f"(interruption)", "DEBUG")
                        final_audio = np.concatenate(
                            [final_audio, curr_part])
                else:
                    # Same host — small silence
                    silence = np.zeros(
                        int(SAMPLE_RATE * SILENCE_MS / 1000),
                        dtype=curr_part.dtype)
                    final_audio = np.concatenate(
                        [final_audio, silence, curr_part])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), final_audio, SAMPLE_RATE)

        if progress_callback:
            progress_callback(100, "✅ Podcast audio complete")
        log(f"  ✅ Podcast saved: {out_path} ({len(final_audio)/SAMPLE_RATE:.1f}s)", "INFO")
        return out_path
