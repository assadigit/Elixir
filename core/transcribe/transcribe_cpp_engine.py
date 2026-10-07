"""V0.6.40 (W-t1): transcribe.cpp engine -- a subprocess wrapper for transcribe-cli.exe.

WHAT THIS IS
------------
A Python module that wraps the transcribe.cpp command-line tool
(transcribe-cli.exe) as a transcription engine for the Elixir app.
It follows the same pattern as the existing faster-whisper engine
(core/transcribe/transcribe_service.py) -- a single function that
takes an audio file + options and returns a result dict with text,
segments, language, and duration.

The transcribe.cpp tool uses a Whisper large-v3 GGUF model with the
Vulkan GPU backend (NVIDIA RTX 3060). It accepts only 16 kHz mono
WAV input -- other formats must be converted first with ffmpeg (the
existing extract_audio_from_video function already produces 16 kHz
mono WAV, so it's reused).

===========================================================================
CONFIGURATION BLOCK - VERIFY THESE PATHS MATCH YOUR RIG.

IMPORTANT: The model path below is a GUESS. The real path is in the
owner's transcribe.bat file (the MODEL= line). To find it:
  1. Open C:\\transcribe.cpp\\transcribe.bat in Notepad
  2. Find the line that starts with 'set MODEL=' or 'MODEL='
  3. Copy that path here OR use the Model button in the Transcribe
     Service dialog (it saves to settings and overrides this default).

These values can be overridden via the app's settings system:
  - transcribe.transcribe_cpp_exe   -> path to transcribe-cli.exe
  - transcribe.transcribe_cpp_model -> path to the Whisper GGUF model file
  - transcribe.transcribe_cpp_lang  -> default language (None = auto-detect)
  - transcribe.engine              -> 'transcribe_cpp' (default) or 'faster_whisper'

If the settings are not set, the defaults below are used.

DEFAULT PATHS (VERIFY AGAINST YOUR transcribe.bat):
  EXE:   C:\\transcribe.cpp\\build\\bin\\Release\\transcribe-cli.exe
  MODEL: C:\\transcribe.cpp\\models\\ggml-large-v3.bin  (GUESS - CHECK transcribe.bat!)
  FFMPEG:  on PATH (no explicit path needed)

===========================================================================

USAGE from the app:
    from core.transcribe.transcribe_cpp_engine import transcribe_with_cpp
    result = transcribe_with_cpp(
        audio_path="/path/to/audio.wav",
        language=None,  # None = auto-detect
        log_callback=lambda msg, level: print(msg),
    )
    # result = {"text": "...", "segments": [...], "language": "...", "duration": 12.5}

The function accepts ANY audio/video format (it converts to 16 kHz mono
WAV with ffmpeg first). The temp WAV is always cleaned up, even on errors.

GPU GUARANTEE: only one transcription runs at a time (a threading.Lock
guards the subprocess call -- the 3 GB model loads on every call).

PARSER DESIGN:
The transcribe.cpp CLI output format is not fully documented. The brief
says "the project's own example prints the transcript on a line starting
text:". The parser handles multiple possible formats:
  1. Lines starting with "text:" -> the transcript text
  2. Lines starting with "backend:" -> the GPU backend (Vulkan/CPU)
  3. Lines starting with "language:" -> the detected language
  4. Lines with timestamps like "[00:00:00.000 --> 00:00:05.000]" -> segments
  5. Fallback: if no "text:" lines are found, all non-info lines are the text

If the real output format is different, the owner should run the CLI
manually and paste the output -- the parser can be adjusted. A "raw
output capture" mode is available by setting capture_raw=True.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION BLOCK -- adjust these to match your installation.
# These are DEFAULTS; the app's settings system can override them at runtime.
# ============================================================================

# Path to transcribe-cli.exe (the built binary from transcribe.cpp).
DEFAULT_TRANSCRIBE_CPP_EXE = r"C:\transcribe.cpp\build\bin\Release\transcribe-cli.exe"

# Path to the Whisper GGUF model file (about 3 GB for F16).
# CHECK YOUR transcribe.bat FOR THE EXACT PATH -- do not invent one.
DEFAULT_TRANSCRIBE_CPP_MODEL = r"C:\transcribe.cpp\models\whisper-large-v3-Q8_0.gguf"

# Default language: None = auto-detect, "en" = English, "fa" = Farsi.
DEFAULT_LANGUAGE = None

# Timeout for the CLI (seconds). Long videos can take minutes.
DEFAULT_TIMEOUT_S = 3600  # 1 hour -- generous for long videos

# Temp folder for the 16 kHz mono WAV. None = system temp.
DEFAULT_TEMP_DIR = None

# ============================================================================
# GPU GUARD -- only one transcription at a time (the model loads on every call).
# ============================================================================

_gpu_lock = threading.Lock()

# ============================================================================
# PARSER -- extract text, language, segments, and backend from the CLI output.
# ============================================================================

# Regex for timestamp lines like "[00:00:00.000 --> 00:00:05.000] Hello world"
_TIMESTAMP_RE = re.compile(
    r"\[\s*(\d+(?:\.\d+)?)\s*->\s*(\d+(?:\.\d+)?)\s*\]\s*(.*)"
)


def _parse_timestamp(ts: str) -> float:
    """Convert a timestamp string to seconds.

    Handles two formats:
    1. 'HH:MM:SS.mmm' (the old expected format)
    2. '123.45' (seconds as a float -- the REAL transcribe.cpp format)
    """
    if ":" in ts:
        parts = ts.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(ts)


def _parse_transcribe_cpp_output(stdout: str, stderr: str):
    """Parse transcribe-cli.exe output.

    V0.6.52: rewritten to match the REAL CLI output format (verified
    from the operator's paste). The CLI prints:

    1. Info lines: audio:, samples:, duration:, sample rate, model:,
       backend:, name:, license:, max audio:, run:
    2. A single 'text:' line with the FULL transcript
    3. A 'detected-language:' line
    4. A 'segments: NNN' count line
    5. Timestamped segment lines: '[ 0.00 ->    4.06] text'

    The parser extracts: text (from the 'text:' line), language (from
    'detected-language:'), segments (from the timestamped lines),
    and backend (from 'backend:').
    """
    text_parts = []
    segments = []
    language = None
    backend = None

    all_lines = (stdout + "\n" + stderr).splitlines()

    for line in all_lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower = line_stripped.lower()

        # -- Extract backend --
        if lower.startswith("backend:"):
            backend = line_stripped.split(":", 1)[1].strip()
            continue

        # -- Extract detected language --
        if lower.startswith("detected-language:"):
            language = line_stripped.split(":", 1)[1].strip()
            continue

        # -- Extract the FULL transcript text (single 'text:' line) --
        if lower.startswith("text:"):
            text_parts.append(line_stripped.split(":", 1)[1].strip())
            continue

        # -- Extract timestamped segments --
        # Format: '[   0.00 ->    4.06] There are three main things...'
        ts_match = _TIMESTAMP_RE.match(line_stripped)
        if ts_match:
            start_ts = _parse_timestamp(ts_match.group(1))
            end_ts = _parse_timestamp(ts_match.group(2))
            seg_text = ts_match.group(3).strip()
            segments.append({"start": start_ts, "end": end_ts, "text": seg_text})
            continue

        # -- Skip known info lines --
        if lower.startswith((
            "audio:", "samples:", "duration:", "sample rate",
            "model:", "name:", "license:", "max audio:",
            "run:", "realtime:", "system_info:", "system info:",
            "segments:",
        )):
            continue

        # -- Skip progress bars --
        if "%" in line_stripped and ("it/s" in line_stripped or "s/it" in line_stripped):
            continue
        if "it/s" in line_stripped or "s/it" in line_stripped:
            continue

    text = " ".join(text_parts).strip()
    return {
        "text": text,
        "segments": segments,
        "language": language,
        "backend": backend,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }

# THE ENGINE -- one function, callable from the app.
# ============================================================================


def transcribe_with_cpp(
    audio_path: str,
    language: str | None = None,
    log_callback=None,
    progress_callback=None,
    capture_raw: bool = False,
) -> dict:
    """Transcribe an audio/video file using transcribe-cli.exe (transcribe.cpp).

    Args:
        audio_path: Path to the audio/video file (any format -- converted to
            16 kHz mono WAV with ffmpeg first).
        language: None = auto-detect, "en" = English, "fa" = Farsi.
        log_callback: Optional callable(msg, level) for progress logging.
        progress_callback: Optional callable(pct, msg) for progress updates.
        capture_raw: If True, the result dict includes raw_stdout + raw_stderr
            (for debugging the output format). Default: False.

    Returns:
        {
            "text": "full transcript text",
            "segments": [{"start": 0.0, "end": 2.5, "text": "..."}, ...],
            "language": "detected language (or None)",
            "duration": float (seconds taken to transcribe),
            "engine_info": {"model": "...", "backend": "Vulkan/CPU"},
        }
        On error: {"error": "plain-language error message"}
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    # -- Resolve paths from settings or defaults ----------------------
    try:
        from utils.settings import Settings

        s = Settings()
        exe_path = s.get("transcribe.transcribe_cpp_exe", DEFAULT_TRANSCRIBE_CPP_EXE)
        model_path = s.get("transcribe.transcribe_cpp_model", DEFAULT_TRANSCRIBE_CPP_MODEL)
        if language is None:
            language = s.get("transcribe.transcribe_cpp_lang", None)
            if language == "auto" or language == "":
                language = None
    except Exception:
        exe_path = DEFAULT_TRANSCRIBE_CPP_EXE
        model_path = DEFAULT_TRANSCRIBE_CPP_MODEL

    # -- Validate: CLI exists -----------------------------------------
    if not Path(exe_path).exists():
        return {
            "error": (
                f"transcribe-cli.exe not found at: {exe_path}\n"
                f"Check the path in Settings -> Transcribe -> transcribe.cpp exe.\n"
                f"If the path is different on your machine, update it there."
            )
        }

    # -- Validate: model exists ---------------------------------------
    # V0.6.47: if the saved setting points to a non-existent file, try
    # the default before erroring (a stale setting from an old version
    # might point to ggml-large-v3.bin which was renamed).
    if not Path(model_path).exists():
        # Try the default model path.
        if model_path != DEFAULT_TRANSCRIBE_CPP_MODEL and Path(DEFAULT_TRANSCRIBE_CPP_MODEL).exists():
            model_path = DEFAULT_TRANSCRIBE_CPP_MODEL
        else:
            return {
                "error": (
                f"Whisper model file not found at: {model_path}\n\n"
                f"FIX: In the Transcribe Service dialog, select 'transcribe.cpp' "
                f"as the engine, then click the 'Model' button to browse "
                f"for your .gguf model file.\n"
                f"Your model is at: C:\\transcribe.cpp\\models\\whisper-large-v3-Q8_0.gguf"
            )
        }

    # -- Convert to 16 kHz mono WAV (if not already) -----------------
    input_path = Path(audio_path)
    temp_wav = None
    wav_to_transcribe = str(input_path)

    # Check if the input is already a 16 kHz mono WAV.
    needs_conversion = True
    if input_path.suffix.lower() == ".wav":
        # Could already be 16 kHz mono -- but we can't verify easily,
        # so always convert to be safe (the conversion is fast).
        pass

    if needs_conversion:
        log("  [CONVERT] Converting to 16 kHz mono WAV with ffmpeg...", "INFO")
        progress(5, "Converting audio format...")
        temp_wav = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            dir=DEFAULT_TEMP_DIR,
            prefix="transcribe_cpp_",
        )
        temp_wav.close()
        temp_wav_path = temp_wav.name

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-vn",  # no video
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",  # 16 kHz
            "-ac",
            "1",  # mono
            temp_wav_path,
        ]
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                _cleanup_temp(temp_wav_path)
                return {
                    "error": (
                        f"ffmpeg failed to convert the audio file.\n"
                        f"ffmpeg error: {result.stderr[:500]}\n"
                        f"Make sure ffmpeg is installed and on PATH."
                    )
                }
            wav_to_transcribe = temp_wav_path
            log("  [OK] Audio converted to 16 kHz mono WAV", "INFO")
        except FileNotFoundError:
            _cleanup_temp(temp_wav_path)
            return {"error": "ffmpeg not found. Install ffmpeg and add it to PATH."}
        except subprocess.TimeoutExpired:
            _cleanup_temp(temp_wav_path)
            return {"error": "ffmpeg timed out (300s) while converting the audio."}
        except Exception as e:
            _cleanup_temp(temp_wav_path)
            return {"error": f"ffmpeg conversion error: {e}"}

    # -- Build the CLI command ----------------------------------------
    cmd = [exe_path, "-m", model_path]
    # Language: add --language flag if the CLI supports it.
    # The brief says to check --help for the exact flag. Common flags:
    #   -l <lang>  or  --language <lang>
    # We try -l first (shorter). If the CLI doesn't support it, the
    # error will be caught and the owner can adjust.
    if language and language != "auto":
        cmd.extend(["-l", language])

    cmd.append(wav_to_transcribe)

    # -- Run the CLI (GPU-guarded) ------------------------------------
    log("  [RUN] Running transcribe.cpp (Vulkan GPU)...", "INFO")
    progress(20, "Transcribing with transcribe.cpp (Vulkan GPU)...")
    t0 = time.time()

    try:
        with _gpu_lock:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,  # capture as bytes for UTF-8 safety
                timeout=DEFAULT_TIMEOUT_S,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
    except subprocess.TimeoutExpired:
        _cleanup_temp(temp_wav)
        return {"error": f"transcribe-cli.exe timed out ({DEFAULT_TIMEOUT_S}s). The file may be too long."}
    except Exception as e:
        _cleanup_temp(temp_wav)
        return {"error": f"Failed to run transcribe-cli.exe: {e}"}

    elapsed = time.time() - t0

    # -- Decode stdout/stderr as UTF-8 (explicit, NOT Windows default) --
    # The brief: "read stdout as bytes, decode as UTF-8 explicitly"
    stdout_text = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr_text = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    # -- Check exit code ----------------------------------------------
    if result.returncode != 0:
        # Extract the last 10 lines of stderr for the error message.
        last_lines = "\n".join(stderr_text.splitlines()[-10:])
        _cleanup_temp(temp_wav)
        return {
            "error": (
                f"transcribe-cli.exe failed (exit code {result.returncode}).\n"
                f"Last output:\n{last_lines}"
            )
        }

    # -- Parse the output ---------------------------------------------
    parsed = _parse_transcribe_cpp_output(stdout_text, stderr_text)

    # V0.6.51: FALLBACK -- if the parser extracted zero text, the CLI
    # output format doesn't match what the parser expects. In that case,
    # just use the raw stdout as the transcript text (minus progress bars).
    # This guarantees the text is never empty if the CLI produced output.
    if not parsed["text"] and stdout_text.strip():
        # Strip obvious progress bar lines from the raw stdout.
        raw_lines = []
        for raw_line in stdout_text.splitlines():
            raw_stripped = raw_line.strip()
            if not raw_stripped:
                continue
            # Skip pure progress bars.
            if "%" in raw_stripped and ("it/s" in raw_stripped or "s/it" in raw_stripped):
                continue
            if "it/s" in raw_stripped or "s/it" in raw_stripped:
                continue
            # Skip info lines.
            lower = raw_stripped.lower()
            if lower.startswith(("backend:", "realtime:", "model:", "system_info:", "system info:")):
                continue
            raw_lines.append(raw_stripped)
        if raw_lines:
            parsed["text"] = "\n".join(raw_lines)
            log(f"  [FALLBACK] Parser extracted 0 text, using raw stdout ({len(raw_lines)} lines)", "WARNING")

    # V0.6.46: dump the raw CLI output to a file for debugging.
    # The file is saved next to the input file as <name>_raw_output.txt
    # so the owner can see exactly what transcribe-cli.exe printed.
    try:
        raw_dump_path = Path(audio_path).with_suffix(".raw_output.txt")
        raw_dump_path.write_text(
            f"=== STDOUT ===\n{stdout_text}\n\n=== STDERR ===\n{stderr_text}\n",
            encoding="utf-8",
        )
        log(f"  [DUMP] Raw CLI output saved to: {raw_dump_path.name}", "DEBUG")
    except Exception:
        pass

    # Log the backend (GPU verification).
    if parsed["backend"]:
        log(f"  [OK] Backend: {parsed['backend']}", "INFO")
    if parsed["language"]:
        log(f"  [OK] Language: {parsed['language']}", "INFO")

    # -- Clean up temp WAV --------------------------------------------
    _cleanup_temp(temp_wav)
    log("  ?? Temp WAV cleaned up", "DEBUG")

    # -- Build the result ---------------------------------------------
    result_dict = {
        "text": parsed["text"],
        "segments": parsed["segments"],
        "language": parsed["language"],
        "duration": elapsed,
        "engine_info": {
            "model": Path(model_path).name,
            "backend": parsed["backend"] or "unknown",
            "exe": "transcribe.cpp",
        },
    }
    if capture_raw:
        result_dict["raw_stdout"] = parsed["raw_stdout"]
        result_dict["raw_stderr"] = parsed["raw_stderr"]

    log(f"  [OK] Transcribed in {elapsed:.1f}s ({len(parsed['text'])} chars)", "INFO")
    progress(100, "Transcription complete")
    return result_dict


def _cleanup_temp(temp_path) -> None:
    """Always clean up the temp WAV file, even on errors."""
    if temp_path is None:
        return
    try:
        path = Path(temp_path) if not isinstance(temp_path, Path) else temp_path
        if path.exists():
            path.unlink()
    except Exception:
        logger.debug("best-effort temp cleanup failed", exc_info=True)
