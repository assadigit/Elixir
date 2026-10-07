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
# V0.6.56 — STREAMING CLI RUNNER. The old subprocess.run(capture_output=True)
# trapped ALL CLI output in memory for the whole transcription: between
# progress(20) and progress(100) the pipeline was completely silent, which is
# exactly the 10-minute "frozen or progressing?" freeze the operator hit on a
# 15-minute video. _stream_cli_output pumps the CLI's stdout/stderr line by
# line into log_callback while it runs (each transcribed line is visible as
# it happens) and maps percent lines to progress_callback.
# ============================================================================

# Percent-line classification (V0.6.56, Task 14 review SHOULD-FIX 1):
# a line moves the progress bar ONLY if it is progress-bar-shaped —
# "### 42%", "### 42% | 120/300 …" — or a whisper progress callback
# ("… progress = 42%"). A transcript line like "text: I am 100% sure"
# contains a percent but is NOT a progress line: it must be echoed,
# never mapped (the old naive regex moved the bar BACKWARD on such
# lines: 48 → 90 → 55).
_PCT_BAR_RE = re.compile(r"^#{1,3}\s*(\d{1,3})\s*%")
_PCT_CALLBACK_RE = re.compile(r"progress\s*=?\s*(\d{1,3})\s*%", re.IGNORECASE)


def _match_percent_line(line: str):
    """Return the int percent if ``line`` is a progress-bar/callback
    line, else None (transcript text mentioning percents is NOT one)."""
    m = _PCT_BAR_RE.match(line)
    if m:
        return int(m.group(1))
    m = _PCT_CALLBACK_RE.search(line)
    if m:
        return int(m.group(1))
    return None


def _stream_cli_output(
    proc,
    log,
    progress,
    *,
    deadline_ts: float | None = None,
    echo_prefix: str = "[whisper]",
):
    """Pump a live CLI subprocess's stdout/stderr into ``log``/``progress``.

    Two daemon reader threads (one per stream) so BOTH streams stream
    concurrently on Windows (``select()`` does not work on pipes there).
    The main loop waits on the process with a 0.5 s poll so the
    ``deadline_ts`` (MONOTONIC seconds, ``time.monotonic()`` — the
    V0.6.55 llamacpp-provider precedent; an NTP clock step must not
    extend a hung CLI run) is enforced even
    when the CLI produces no output at all: on expiry the process is
    KILLED and ``timed_out=True`` comes back.

    Echo contract (what the operator sees in the live log):
      - every stdout/stderr line, prefixed ``"  [whisper] ..."`` so CLI
        lines are distinguishable from [LLM]/[CONVERT] lines;
      - ``\\r`` spinner frames collapse to the LATEST frame (the log
        shows the current percent, not the animation);
      - a PROGRESS-BAR-SHAPED line (see _match_percent_line) is echoed
        + mapped to ``progress(20+pct*0.7)`` ONLY when the integer
        percent CHANGES (spinner spam dedup); transcript lines that
        merely CONTAIN a percent are echoed but never mapped.

    Returns ``(stdout_text, stderr_text, returncode, timed_out)``. The
    accumulated text is BYTE-FAITHFUL to what ``capture_output=True``
    produced (the P6 parser's input is unchanged — the ECHO path
    collapses spinner frames, the ACCUMULATION never does).
    """
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    state = {"pct": -1}

    def _pump(stream, parts) -> None:
        if stream is None:
            return
        try:
            for raw in stream:
                if isinstance(raw, (bytes, bytearray)):
                    chunk = raw.decode("utf-8", errors="replace")
                else:
                    chunk = str(raw)
                parts.append(chunk)
                visible = chunk.split("\r")[-1].rstrip("\n").strip()
                if not visible:
                    continue
                try:
                    pct = _match_percent_line(visible)
                    if pct is not None:
                        if pct == state["pct"]:
                            continue  # spinner frame / repeated percent — dedup
                        state["pct"] = pct
                        log(f"  {echo_prefix} {visible}", "INFO")
                        progress(20 + int(pct * 0.7), f"Transcribing with transcribe.cpp… {pct}%")
                        continue
                    log(f"  {echo_prefix} {visible}", "INFO")
                except Exception:
                    # A raising callback must never truncate the stream —
                    # the accumulated text is the parser's input.
                    logger.debug("best-effort echo failed", exc_info=True)
        except Exception:
            logger.debug("stream pump ended (stream closed)", exc_info=True)

    threads = [
        threading.Thread(target=_pump, args=(proc.stdout, stdout_parts), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, stderr_parts), daemon=True),
    ]
    for t in threads:
        t.start()

    timed_out = False
    while True:
        try:
            proc.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if deadline_ts is not None and time.monotonic() > deadline_ts:
                timed_out = True
                try:
                    proc.kill()
                except Exception:
                    logger.debug("best-effort kill failed", exc_info=True)
                try:
                    proc.wait()
                except Exception:
                    logger.debug("best-effort post-kill wait failed", exc_info=True)
                break

    for t in threads:
        t.join(timeout=5)

    returncode = proc.returncode
    if returncode is None:
        returncode = -1
    return "".join(stdout_parts), "".join(stderr_parts), returncode, timed_out

# ============================================================================
# PARSER -- extract text, language, segments, and backend from the CLI output.
# ============================================================================

# Regex for timestamp lines like "[00:00:00.000 --> 00:00:05.000] Hello world"
# V0.6.55 (P6): the timestamp body accepts the three observed dialects
# (bare seconds "12.34", two-part "MM:SS.mmm", three-part
# "HH:MM:SS.mmm") and BOTH arrow styles ("->" the transcribe.cpp
# dialect, "-->" the whisper.cpp dialect — the V0.6.52 regex only
# matched single-arrow bare-seconds and silently dropped everything
# else).
_TIMESTAMP_RE = re.compile(
    r"\[\s*(\d+(?::\d+(?::\d+)?)?(?:\.\d+)?)\s*-{1,2}>\s*"
    r"(\d+(?::\d+(?::\d+)?)?(?:\.\d+)?)\s*\]\s*(.*)"
)

# V0.6.55 (P6): progress-bar lines that carry a percentage bar but no
# it/s marker (the transcribe.cpp style "12%|████| 00:12<00:34").
_PROGRESS_BAR_RE = re.compile(r"^\s*\d{1,3}%\s*\|")

# V0.6.55 (P6): the info-line prefixes that STOP a text continuation
# block (everything the CLI prefixes its metadata with, both dialects).
_INFO_PREFIXES = (
    "audio:", "samples:", "duration:", "sample rate", "model:",
    "name:", "license:", "max audio:", "run:", "realtime:",
    "system_info:", "system info:", "segments:", "backend:",
    "detected-language:", "detected language:", "text:",
)


def _parse_timestamp(ts: str) -> float:
    """Convert a timestamp string to seconds.

    Handles the observed formats (V0.6.55: also the 2-part form):
    1. 'HH:MM:SS.mmm' (the whisper.cpp form)
    2. 'MM:SS.mmm' (the two-part form)
    3. '123.45' (seconds as a float -- the transcribe.cpp form)
    """
    if ":" in ts:
        parts = ts.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        # Degenerate (1 part with a colon?) — treat as seconds.
        return float(parts[0])
    return float(ts)


def _parse_one_cli_line(line, in_text_block, text_parts, segments):
    """V0.6.55 (P6, Task 9 review refactor): parse ONE CLI output line.

    Mutates ``text_parts`` / ``segments`` in place; returns the line's
    findings as ``{"language": str | None, "backend": str | None,
    "in_text_block": bool}`` so the caller can fold the metadata and
    carry the continuation-block state across lines (never across
    streams).
    """
    line_stripped = line.strip()
    if not line_stripped:
        return {"language": None, "backend": None, "in_text_block": in_text_block}

    lower = line_stripped.lower()

    # -- Extract backend --
    if lower.startswith("backend:"):
        backend = line_stripped.split(":", 1)[1].strip()
        return {"language": None, "backend": backend, "in_text_block": False}

    # -- Extract detected language (both spellings) --
    if lower.startswith(("detected-language:", "detected language:")):
        language = line_stripped.split(":", 1)[1].strip()
        return {"language": language, "backend": None, "in_text_block": False}

    # -- Extract the FULL transcript text (single 'text:' line,
    #    V0.6.55: possibly wrapped onto continuation lines) --
    if lower.startswith("text:"):
        text_parts.append(line_stripped.split(":", 1)[1].strip())
        return {"language": None, "backend": None, "in_text_block": True}

    # -- Extract timestamped segments --
    # Format: '[   0.00 ->    4.06] There are three main things...'
    # (or '[00:00:00.000 --> 00:00:05.000] ...' -- the whisper.cpp
    # dialect, V0.6.55)
    ts_match = _TIMESTAMP_RE.match(line_stripped)
    if ts_match:
        start_ts = _parse_timestamp(ts_match.group(1))
        end_ts = _parse_timestamp(ts_match.group(2))
        seg_text = ts_match.group(3).strip()
        segments.append({"start": start_ts, "end": end_ts, "text": seg_text})
        return {"language": None, "backend": None, "in_text_block": False}

    # -- Skip known info lines (they also END a text block) --
    if lower.startswith(_INFO_PREFIXES[:-1]):  # every prefix except 'text:'
        return {"language": None, "backend": None, "in_text_block": False}

    # -- Skip progress bars (it/s, s/it, or a percent bar) --
    if "%" in line_stripped and ("it/s" in line_stripped or "s/it" in line_stripped):
        return {"language": None, "backend": None, "in_text_block": in_text_block}
    if "it/s" in line_stripped or "s/it" in line_stripped:
        return {"language": None, "backend": None, "in_text_block": in_text_block}
    if _PROGRESS_BAR_RE.match(line_stripped):
        return {"language": None, "backend": None, "in_text_block": in_text_block}

    # -- V0.6.55 (P6): continuation of a wrapped 'text:' block --
    if in_text_block:
        text_parts.append(line_stripped)
        return {"language": None, "backend": None, "in_text_block": True}
    # (Anything else -- noise we do not recognize -- is dropped, the
    # pre-V0.6.55 behavior.)
    return {"language": None, "backend": None, "in_text_block": in_text_block}


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

    V0.6.55 (P6) -- the edge-case hardening (each was a silent DROP):
      - 'detected language:' (space variant) recognized alongside the
        hyphen form;
      - BOTH arrow dialects ('->' and '-->') and ALL THREE timestamp
        forms (seconds / MM:SS.mmm / HH:MM:SS.mmm) parse as segments;
      - lines WRAPPING a long 'text:' value (no prefix) continue the
        text block until an info prefix / timestamp line ends it;
      - an output with ONLY timestamped segments (no 'text:' line)
        builds its text by joining the segment texts (instead of
        falling to the raw-stdout fallback with the info lines);
      - a UTF-8 BOM on the first line is stripped;
      - progress bars with a percent bar but no it/s marker are
        skipped.

    Task 9 review fix: stdout and stderr are parsed as SEPARATE
    streams. The old ``stdout + "\n" + stderr`` concatenation let a
    stdout ending in a ``text:`` block swallow every unrecognized
    STDERR line (model-load chatter, warnings) into the transcript.
    Metadata (backend, language) and segments still come from either
    stream (the V0.6.52 contract); the text continuation block can
    never cross the stream boundary.
    """
    text_parts: list[str] = []
    segments = []
    language = None
    backend = None

    # V0.6.55 (P6): a UTF-8 BOM on the first line would poison the
    # first prefix match -- strip it before splitting.
    stdout_clean = (stdout or "").lstrip("\ufeff")
    stderr_clean = (stderr or "").lstrip("\ufeff")

    for stream_lines in (stdout_clean.splitlines(), stderr_clean.splitlines()):
        in_text_block = False  # a text block never crosses streams
        for line in stream_lines:
            parsed = _parse_one_cli_line(line, in_text_block, text_parts, segments)
            if parsed["language"] is not None:
                language = parsed["language"]
            if parsed["backend"] is not None:
                backend = parsed["backend"]
            in_text_block = parsed["in_text_block"]

    if text_parts:
        text = " ".join(p for p in text_parts if p).strip()
    elif segments:
        # V0.6.55 (P6): no 'text:' line but segments exist -- the
        # transcript is the joined segment texts (NOT the raw-stdout
        # fallback, which drags info lines along).
        text = " ".join(seg["text"] for seg in segments if seg["text"]).strip()
    else:
        text = ""

    return {
        "text": text,
        "segments": segments,
        "language": language,
        "backend": backend,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


def _convert_to_wav16k(input_path: Path, log, progress):
    """V0.6.56: the ffmpeg 16 kHz mono WAV conversion, extracted from
    transcribe_with_cpp (every log line, progress number and error
    string is verbatim — only its home moved).

    Returns ``(wav_to_transcribe, temp_wav_path)`` on success (the temp
    path is a PATH STRING — the old code kept the NamedTemporaryFile
    object in ``temp_wav`` and later handed the OBJECT to
    ``_cleanup_temp``, whose ``Path(temp_path)`` raised TypeError into
    the best-effort except — the temp WAVs were never actually deleted;
    the string path actually deletes them now), or an ``{"error": …}``
    dict on failure (the legacy strings, verbatim).
    """
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
        log("  [OK] Audio converted to 16 kHz mono WAV", "INFO")
        return temp_wav_path, temp_wav_path
    except FileNotFoundError:
        _cleanup_temp(temp_wav_path)
        return {"error": "ffmpeg not found. Install ffmpeg and add it to PATH."}
    except subprocess.TimeoutExpired:
        _cleanup_temp(temp_wav_path)
        return {"error": "ffmpeg timed out (300s) while converting the audio."}
    except Exception as e:
        _cleanup_temp(temp_wav_path)
        return {"error": f"ffmpeg conversion error: {e}"}


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
    # V0.6.56: the ffmpeg conversion moved to its own helper so
    # transcribe_with_cpp contains NO subprocess.run call — the whisper
    # CLI call is Popen+streamed (see _stream_cli_output), and keeping
    # the ffmpeg run out of the function keeps that contract absolute.
    input_path = Path(audio_path)
    converted = _convert_to_wav16k(input_path, log, progress)
    if isinstance(converted, dict):
        # an {"error": ...} — the legacy strings, verbatim.
        return converted
    wav_to_transcribe, temp_wav = converted

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

    # -- Run the CLI (GPU-guarded, STREAMING) --------------------------
    # V0.6.56: the old subprocess.run(capture_output=True) trapped ALL
    # CLI output in memory for the whole transcription — between
    # progress(20) and progress(100) the pipeline was completely
    # silent, which is exactly the 10-minute "frozen or progressing?"
    # freeze the operator hit on a 15-minute video. The CLI now runs
    # via Popen and _stream_cli_output pumps stdout/stderr line by
    # line into log_callback (each transcribed line is visible as it
    # happens) and maps percent lines onto the progress bar.
    log("  [RUN] Running transcribe.cpp (Vulkan GPU)...", "INFO")
    progress(20, "Transcribing with transcribe.cpp (Vulkan GPU)...")
    t0 = time.time()

    try:
        with _gpu_lock:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            try:
                stdout_text, stderr_text, returncode, timed_out = _stream_cli_output(
                    proc,
                    log,
                    progress,
                    deadline_ts=time.monotonic() + DEFAULT_TIMEOUT_S,
                )
            except Exception:
                # The streamer itself exploded after Popen — kill the CLI
                # or it leaks, holding the GPU + filling a pipe nobody
                # drains; the outer handler renders the error.
                try:
                    proc.kill()
                except Exception:
                    logger.debug("best-effort kill after streamer failure failed", exc_info=True)
                raise
    except Exception as e:  # noqa: BLE001 — Popen failure (exe missing, etc.)
        _cleanup_temp(temp_wav)
        return {"error": f"Failed to run transcribe-cli.exe: {e}"}

    elapsed = time.time() - t0

    if timed_out:
        # The same legacy contract as subprocess.run(timeout=…) raising
        # TimeoutExpired — the exact string operators/triage know.
        _cleanup_temp(temp_wav)
        return {"error": f"transcribe-cli.exe timed out ({DEFAULT_TIMEOUT_S}s). The file may be too long."}

    # -- Check exit code ----------------------------------------------
    if returncode != 0:
        # Extract the last 10 lines of stderr for the error message.
        last_lines = "\n".join(stderr_text.splitlines()[-10:])
        _cleanup_temp(temp_wav)
        return {
            "error": (
                f"transcribe-cli.exe failed (exit code {returncode}).\n"
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
