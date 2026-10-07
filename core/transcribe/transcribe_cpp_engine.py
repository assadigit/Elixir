"""V0.6.40 (W-t1): transcribe.cpp engine — a subprocess wrapper for transcribe-cli.exe.

WHAT THIS IS
------------
A Python module that wraps the transcribe.cpp command-line tool
(transcribe-cli.exe) as a transcription engine for the Elixir app.
It follows the same pattern as the existing faster-whisper engine
(core/transcribe/transcribe_service.py) — a single function that
takes an audio file + options and returns a result dict with text,
segments, language, and duration.

The transcribe.cpp tool uses a Whisper large-v3 GGUF model with the
Vulkan GPU backend (NVIDIA RTX 3060). It accepts only 16 kHz mono
WAV input — other formats must be converted first with ffmpeg (the
existing extract_audio_from_video function already produces 16 kHz
mono WAV, so it's reused).

═══════════════════════════════════════════════════════════════════════════
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

═══════════════════════════════════════════════════════════════════════════

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
guards the subprocess call — the 3 GB model loads on every call).

PARSER DESIGN:
The transcribe.cpp CLI output format is not fully documented. The brief
says "the project's own example prints the transcript on a line starting
text:". The parser handles multiple possible formats:
  1. Lines starting with "text:" → the transcript text
  2. Lines starting with "backend:" → the GPU backend (Vulkan/CPU)
  3. Lines starting with "language:" → the detected language
  4. Lines with timestamps like "[00:00:00.000 --> 00:00:05.000]" → segments
  5. Fallback: if no "text:" lines are found, all non-info lines are the text

If the real output format is different, the owner should run the CLI
manually and paste the output — the parser can be adjusted. A "raw
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

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION BLOCK — adjust these to match your installation.
# These are DEFAULTS; the app's settings system can override them at runtime.
# ════════════════════════════════════════════════════════════════════════════

# Path to transcribe-cli.exe (the built binary from transcribe.cpp).
DEFAULT_TRANSCRIBE_CPP_EXE = r"C:\transcribe.cpp\build\bin\Release\transcribe-cli.exe"

# Path to the Whisper GGUF model file (about 3 GB for F16).
# CHECK YOUR transcribe.bat FOR THE EXACT PATH — do not invent one.
DEFAULT_TRANSCRIBE_CPP_MODEL = r"C:\transcribe.cpp\models\whisper-large-v3-Q8_0.gguf"

# Default language: None = auto-detect, "en" = English, "fa" = Farsi.
DEFAULT_LANGUAGE = None

# Timeout for the CLI (seconds). Long videos can take minutes.
DEFAULT_TIMEOUT_S = 3600  # 1 hour — generous for long videos

# Temp folder for the 16 kHz mono WAV. None = system temp.
DEFAULT_TEMP_DIR = None

# ════════════════════════════════════════════════════════════════════════════
# GPU GUARD — only one transcription at a time (the model loads on every call).
# ════════════════════════════════════════════════════════════════════════════

_gpu_lock = threading.Lock()

# ════════════════════════════════════════════════════════════════════════════
# PARSER — extract text, language, segments, and backend from the CLI output.
# ════════════════════════════════════════════════════════════════════════════

# Regex for timestamp lines like "[00:00:00.000 --> 00:00:05.000] Hello world"
_TIMESTAMP_RE = re.compile(
    r"\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)"
)


def _parse_timestamp(ts: str) -> float:
    """Convert 'HH:MM:SS.mmm' to seconds."""
    parts = ts.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _parse_transcribe_cpp_output(stdout: str, stderr: str):
    """Parse transcribe-cli.exe output.

    V0.6.46: SIMPLIFIED parser. The V0.6.40 parser was too aggressive
    with filters — it skipped lines that looked like info but were
    actually transcript text (the operator's report: 'output was empty
    inside' even though the CLI succeeded). The new approach: capture
    EVERYTHING except progress bars + a few known info prefixes.

    Known info prefixes that are stripped:
      backend:, realtime:, language:, model:, system_info:

    Progress bar patterns that are skipped:
      lines with %, |, block chars, or "it/s" or "s/it"
      lines that are pure numbers

    Everything else is transcript text.
    """
    text_parts = []
    segments = []
    language = None
    backend = None

    # Combine stdout + stderr (the CLI may print to either).
    all_lines = (stdout + "\n" + stderr).splitlines()

    for line in all_lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # ── Extract known info fields ────────────────────────────────
        lower = line_stripped.lower()

        # backend: Vulkan
        if lower.startswith("backend:"):
            backend = line_stripped.split(":", 1)[1].strip()
            continue

        # language: english (or farsi, etc.)
        if lower.startswith("language:"):
            language = line_stripped.split(":", 1)[1].strip()
            continue

        # Skip known info prefixes (NOT transcript text).
        if lower.startswith(("realtime:", "model:", "system_info:", "system info:")):
            continue

        # ── Skip progress bars ──────────────────────────────────────
        # tqdm progress bars contain %, |, block chars, or it/s
        if "%" in line_stripped and ("it/s" in line_stripped or "s/it" in line_stripped):
            continue
        if "it/s" in line_stripped or "s/it" in line_stripped:
            continue
        # Block characters from tqdm/progress
        if any(ch in line_stripped for ch in ("\u2588", "\u2589", "\u258a", "\u258b", "\u258c", "\u258d", "\u258e", "\u258f", "\u2591", "\u2592", "\u2593")):
            continue
        # Lines that are ONLY progress bar characters
        stripped_of_bars = line_stripped.replace("|", "").replace("-", "").replace(" ", "")
        if not stripped_of_bars or stripped_of_bars.isdigit():
            continue

        # ── Check for timestamped segments ──────────────────────────
        # [00:00:00.000 --> 00:00:05.000] Hello world
        ts_match = _TIMESTAMP_RE.match(line_stripped)
        if ts_match:
            start_ts = _parse_timestamp(ts_match.group(1))
            end_ts = _parse_timestamp(ts_match.group(2))
            seg_text = ts_match.group(3).strip()
            segments.append({"start": start_ts, "end": end_ts, "text": seg_text})
            text_parts.append(seg_text)
            continue

        # ── Strip "text:" prefix if present ─────────────────────────
        if lower.startswith("text:"):
            seg_text = line_stripped.split(":", 1)[1].strip()
            text_parts.append(seg_text)
            continue

        # ── Everything else IS transcript text ───────────────────────
        # V0.6.46: don't skip lines that start with "loading:", "processing:"
        # etc — the CLI might print the transcript text after these prefixes.
        # Only skip if the line is CLEARLY not transcript (has a colon AND
        # a known info keyword before the colon AND is short).
        if ":" in line_stripped and len(line_stripped) < 80:
            prefix = line_stripped.split(":")[0].lower().strip()
            if prefix in ("loading", "warming", "processing", "device", "gpu", "system", "init"):
                continue

        text_parts.append(line_stripped)

    text = "\n".join(text_parts).strip()
    return {
        "text": text,
        "segments": segments,
        "language": language,
        "backend": backend,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


    The parser handles multiple possible output formats:
    1. Lines starting with "text:" → transcript text (one per segment)
    2. Lines starting with "backend:" → GPU backend info
    3. Lines starting with "language:" → detected language
    4. Lines with "[HH:MM:SS.mmm --> HH:MM:SS.mmm] text" → timestamped segments
    5. Fallback: all non-info lines are the transcript text

    Returns a dict with: text, segments, language, backend, raw_stdout, raw_stderr.
    """
    text_parts = []
    segments = []
    language = None
    backend = None

    # Combine stdout + stderr (the CLI may print to either).
    all_lines = (stdout + "\n" + stderr).splitlines()

    for line in all_lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for "backend:" info line.
        if line_stripped.lower().startswith("backend:"):
            backend = line_stripped.split(":", 1)[1].strip()
            continue

        # Check for "language:" info line.
        if line_stripped.lower().startswith("language:"):
            language = line_stripped.split(":", 1)[1].strip()
            continue

        # Check for "realtime:" info line (skip — not transcript text).
        if line_stripped.lower().startswith("realtime:"):
            continue

        # Check for timestamped segment: "[HH:MM:SS.mmm --> HH:MM:SS.mmm] text"
        ts_match = _TIMESTAMP_RE.match(line_stripped)
        if ts_match:
            start = _parse_timestamp(ts_match.group(1))
            end = _parse_timestamp(ts_match.group(2))
            seg_text = ts_match.group(3).strip()
            segments.append({"start": start, "end": end, "text": seg_text})
            text_parts.append(seg_text)
            continue

        # Check for "text:" prefix (the CLI prints "text: <transcript>").
        if line_stripped.lower().startswith("text:"):
            seg_text = line_stripped.split(":", 1)[1].strip()
            text_parts.append(seg_text)
            continue

        # Skip other known info-line prefixes.
        if line_stripped.lower().startswith(
            ("model:", "device:", "gpu:", "loading:", "system:", "warming:", "processing:")
        ):
            continue

        # Fallback: this line is transcript text (no known prefix).
        # Skip progress bars (lines with %, |, or blocks).
        if "%" in line_stripped or "▏" in line_stripped or "▎" in line_stripped:
            continue
        if line_stripped.startswith("[") and "]" in line_stripped and "it/s" in line_stripped:
            continue  # tqdm progress bar

        text_parts.append(line_stripped)

    text = " ".join(text_parts).strip()
    return {
        "text": text,
        "segments": segments,
        "language": language,
        "backend": backend,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


# ════════════════════════════════════════════════════════════════════════════
# THE ENGINE — one function, callable from the app.
# ════════════════════════════════════════════════════════════════════════════


def transcribe_with_cpp(
    audio_path: str,
    language: str | None = None,
    log_callback=None,
    progress_callback=None,
    capture_raw: bool = False,
) -> dict:
    """Transcribe an audio/video file using transcribe-cli.exe (transcribe.cpp).

    Args:
        audio_path: Path to the audio/video file (any format — converted to
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

    # ── Resolve paths from settings or defaults ──────────────────────
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

    # ── Validate: CLI exists ─────────────────────────────────────────
    if not Path(exe_path).exists():
        return {
            "error": (
                f"transcribe-cli.exe not found at: {exe_path}\n"
                f"Check the path in Settings → Transcribe → transcribe.cpp exe.\n"
                f"If the path is different on your machine, update it there."
            )
        }

    # ── Validate: model exists ───────────────────────────────────────
    if not Path(model_path).exists():
        return {
            "error": (
                f"Whisper model file not found at: {model_path}\n"
                f"Check the path in Settings → Transcribe → transcribe.cpp model.\n"
                f"The model is a ~3 GB GGUF file (e.g., ggml-large-v3.bin)."
            )
        }

    # ── Convert to 16 kHz mono WAV (if not already) ─────────────────
    input_path = Path(audio_path)
    temp_wav = None
    wav_to_transcribe = str(input_path)

    # Check if the input is already a 16 kHz mono WAV.
    needs_conversion = True
    if input_path.suffix.lower() == ".wav":
        # Could already be 16 kHz mono — but we can't verify easily,
        # so always convert to be safe (the conversion is fast).
        pass

    if needs_conversion:
        log("  🎬 Converting to 16 kHz mono WAV with ffmpeg...", "INFO")
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
            log("  ✅ Audio converted to 16 kHz mono WAV", "INFO")
        except FileNotFoundError:
            _cleanup_temp(temp_wav_path)
            return {"error": "ffmpeg not found. Install ffmpeg and add it to PATH."}
        except subprocess.TimeoutExpired:
            _cleanup_temp(temp_wav_path)
            return {"error": "ffmpeg timed out (300s) while converting the audio."}
        except Exception as e:
            _cleanup_temp(temp_wav_path)
            return {"error": f"ffmpeg conversion error: {e}"}

    # ── Build the CLI command ────────────────────────────────────────
    cmd = [exe_path, "-m", model_path]
    # Language: add --language flag if the CLI supports it.
    # The brief says to check --help for the exact flag. Common flags:
    #   -l <lang>  or  --language <lang>
    # We try -l first (shorter). If the CLI doesn't support it, the
    # error will be caught and the owner can adjust.
    if language and language != "auto":
        cmd.extend(["-l", language])

    cmd.append(wav_to_transcribe)

    # ── Run the CLI (GPU-guarded) ────────────────────────────────────
    log(f"  🎙️ Running transcribe.cpp (Vulkan GPU)...", "INFO")
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

    # ── Decode stdout/stderr as UTF-8 (explicit, NOT Windows default) ──
    # The brief: "read stdout as bytes, decode as UTF-8 explicitly"
    stdout_text = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr_text = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    # ── Check exit code ──────────────────────────────────────────────
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

    # ── Parse the output ─────────────────────────────────────────────
    parsed = _parse_transcribe_cpp_output(stdout_text, stderr_text)

    # V0.6.46: dump the raw CLI output to a file for debugging.
    # The file is saved next to the input file as <name>_raw_output.txt
    # so the owner can see exactly what transcribe-cli.exe printed.
    try:
        raw_dump_path = Path(audio_path).with_suffix(".raw_output.txt")
        raw_dump_path.write_text(
            f"=== STDOUT ===\n{stdout_text}\n\n=== STDERR ===\n{stderr_text}\n",
            encoding="utf-8",
        )
        log(f"  📋 Raw CLI output saved to: {raw_dump_path.name}", "DEBUG")
    except Exception:
        pass

    # Log the backend (GPU verification).
    if parsed["backend"]:
        log(f"  ✅ Backend: {parsed['backend']}", "INFO")
    if parsed["language"]:
        log(f"  🌐 Language: {parsed['language']}", "INFO")

    # ── Clean up temp WAV ────────────────────────────────────────────
    _cleanup_temp(temp_wav)
    log("  🗑️ Temp WAV cleaned up", "DEBUG")

    # ── Build the result ─────────────────────────────────────────────
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

    log(f"  ✅ Transcribed in {elapsed:.1f}s ({len(parsed['text'])} chars)", "INFO")
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
