"""V11.78.0: Transcription service — video/audio → text + Obsidian summary.

Pipeline:
1. Extract audio from video (ffmpeg) — or use audio file directly
2. Transcribe with faster-whisper (CTranslate2, GPU-accelerated)
3. Output raw transcript
4. Summarize with Ollama LLM → Obsidian-friendly markdown

Model recommendations:
- tiny:    ~39 MB, fastest, lower accuracy — for quick drafts
- base:    ~74 MB, fast, decent accuracy — for meetings
- small:   ~244 MB, good balance — recommended default
- medium:  ~769 MB, high accuracy — for important content
- large-v3: ~1.5 GB, best accuracy — for final publications

GPU: uses CTranslate2 with INT8 quantization — 4x faster than openai/whisper
CPU: falls back automatically (slower but works)
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

# V18.20.4.12 (W-a10) follow-up: the DEFAULT model tag here was the
# KNOWN-BAD "…-Q4_K_M:latest" variant that 404s on the rig (the dialog
# combo already uses RIG_FALLBACK_MODEL; the service default now matches
# so programmatic callers don't hit the dead tag).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from core.system.timeouts import LONG_RUN_TIMEOUT_S

logger = logging.getLogger(__name__)


def extract_audio_from_video(
    video_path: str,
    output_path: str,
    log_callback=None,
) -> bool:
    """Extract audio from a video file using ffmpeg.

    Converts to 16kHz mono WAV (Whisper's required format).
    Returns True on success, False on failure.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",  # no video
        "-acodec",
        "pcm_s16le",  # 16-bit PCM
        "-ar",
        "16000",  # 16kHz
        "-ac",
        "1",  # mono
        str(output_path),
    ]

    try:
        log(f"  🎬 Extracting audio from {Path(video_path).name}...", "INFO")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=LONG_RUN_TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode != 0:
            log(f"  ❌ ffmpeg failed: {result.stderr[:300]}", "ERROR")
            return False
        log(f"  ✅ Audio extracted: {Path(output_path).name}", "INFO")
        return True
    except FileNotFoundError:
        log("  ❌ ffmpeg not found. Install ffmpeg and add it to PATH.", "ERROR")
        return False
    except subprocess.TimeoutExpired:
        log("  ❌ ffmpeg timed out (600s)", "ERROR")
        return False
    except Exception as e:
        log(f"  ❌ ffmpeg error: {e}", "ERROR")
        return False


def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    device: str = "auto",
    compute_type: str = "auto",
    language: str = "auto",
    log_callback=None,
    progress_callback=None,
    engine: str = "transcribe_cpp",
) -> dict:
    """Transcribe audio file.

    V0.6.42: the DEFAULT engine is now transcribe.cpp (Vulkan GPU,
    Whisper large-v3 GGUF). The old faster-whisper engine is still
    available — pass engine="faster_whisper" or set the
    ``transcribe.engine`` setting to "faster_whisper".

    Args:
        audio_path: Path to the audio file (WAV, MP3, etc.)
        model_size: faster-whisper only: "tiny", "base", "small",
            "medium", "large-v3" (ignored by transcribe.cpp)
        device: faster-whisper only: "auto", "cuda", or "cpu"
        compute_type: faster-whisper only: "auto", "int8", etc.
        language: "auto" for auto-detection, or "en", "fa", etc.
        log_callback: Optional callable(msg, level)
        progress_callback: Optional callable(pct, msg)
        engine: "transcribe_cpp" (default — Vulkan GPU) or
            "faster_whisper" (CTranslate2, the old engine)

    Returns:
        {
            "text": "full transcript text",
            "segments": [{"start": 0.0, "end": 2.5, "text": "..."}, ...],
            "language": "detected language",
            "duration": float (seconds),
        }
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    # V0.6.42: resolve the engine from settings if not explicitly passed.
    if engine == "transcribe_cpp":
        # Check if the setting overrides to faster_whisper.
        try:
            from utils.settings import Settings

            s = Settings()
            engine = s.get("transcribe.engine", "transcribe_cpp")
        except Exception:
            pass  # keep the default

    # ── V0.6.42: dispatch to transcribe.cpp ──────────────────────────
    if engine == "transcribe_cpp":
        log("  🎙️ Using transcribe.cpp (Vulkan GPU, Whisper large-v3 GGUF)", "INFO")
        progress(5, "Transcribing with transcribe.cpp (Vulkan GPU)...")
        try:
            from core.transcribe.transcribe_cpp_engine import transcribe_with_cpp

            return transcribe_with_cpp(
                audio_path=audio_path,
                language=None if language == "auto" else language,
                log_callback=log_callback,
                progress_callback=progress_callback,
            )
        except ImportError:
            return {"error": "transcribe.cpp engine module not found."}
        except Exception as e:
            return {"error": f"transcribe.cpp engine error: {e}"}

    # ── Old engine: faster-whisper (kept for fallback) ───────────────
    log(f"  🎙️ Using faster-whisper (model={model_size})", "INFO")

    # Resolve device
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    # Resolve compute type
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    log(f"  🎙️ Loading whisper model '{model_size}' on {device} ({compute_type})...", "INFO")
    progress(5, f"Loading model '{model_size}'...")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"error": "faster-whisper not installed. Run: pip install faster-whisper"}

    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
    except Exception:
        log(f"  ⚠️ Failed to load on {device}/{compute_type}, trying CPU/int8...", "WARNING")
        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e2:
            return {"error": f"Failed to load model: {e2}"}

    log("  ✅ Model loaded. Transcribing...", "INFO")
    progress(20, "Transcribing audio...")

    # Transcribe
    try:
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=None if language == "auto" else language,
            beam_size=5,
            vad_filter=True,
        )

        segments = []
        full_text_parts = []
        total_duration = info.duration if hasattr(info, "duration") else 0

        for i, segment in enumerate(segments_iter):
            segments.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                }
            )
            full_text_parts.append(segment.text.strip())

            # Update progress
            if total_duration > 0:
                pct = 20 + int(70 * segment.end / total_duration)
                progress(min(90, pct), f"Transcribing... {segment.end:.0f}s/{total_duration:.0f}s")
            else:
                progress(50, f"Transcribing... segment {i + 1}")

        full_text = " ".join(full_text_parts)

        log(
            f"  ✅ Transcription complete: {len(segments)} segments, "
            f"{len(full_text)} chars, language: {info.language}",
            "INFO",
        )

        return {
            "text": full_text,
            "segments": segments,
            "language": info.language,
            "duration": total_duration,
        }

    except Exception as e:
        return {"error": f"Transcription failed: {e}"}


def format_transcript_with_timestamps(segments: list) -> str:
    """Format transcript segments with timestamps for readable output."""
    lines = []
    for seg in segments:
        start_mins = int(seg["start"] // 60)
        start_secs = seg["start"] % 60
        timestamp = f"[{start_mins:02d}:{start_secs:05.2f}]"
        lines.append(f"{timestamp} {seg['text']}")
    return "\n\n".join(lines)


def summarize_transcript(
    transcript: str,
    model: str = RIG_FALLBACK_MODEL,
    ollama_url: str = "http://localhost:11434",
    log_callback=None,
    progress_callback=None,
    output_type: str = "summary",
) -> str:
    """Summarize transcript into Obsidian-friendly markdown using Ollama.

    V13.28.0 (P2.10): Now delegates to ``llm_provider.create_provider()`` +
    ``complete_streaming()`` instead of direct ``requests.post``. Gets:
    - OllamaSupervisor crash recovery (auto-restart after 3 failures)
    - Retry with backoff
    - Proxy-proof HTTP (safe_ollama_request pattern)
    - <think> block stripping (via response_parser)

    Returns the summarized markdown, or an error string.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    import re

    from core.summarisation.prompt_manager import PromptManager

    _pm = PromptManager()
    # V0.6.43: select the prompt template based on output_type.
    if output_type == "tutorial":
        prompt = _pm.render_template(
            "transcribe/transcript_tutorial",
            transcript=transcript[:8000],
        )
        log("  Generating tutorial/educational guide...", "INFO")
        progress(92, "Generating tutorial guide with LLM...")
    else:
        prompt = _pm.render_template(
            "transcribe/transcript_notes",
            transcript=transcript[:8000],
        )
        log("  Summarizing transcript (core concepts + key takeaways)...", "INFO")
        progress(92, "Summarizing with LLM...")

    log(f"  📝 Summarizing transcript with {model}...", "INFO")
    progress(92, "Summarizing with LLM...")

    try:
        from core.llm.llm_provider import create_provider
        from core.summarisation.response_parser import strip_thinking
        from utils.settings import Settings

        s = Settings()
        # V0.6.0 (T2): provider now follows the configured
        # ``summarisation.provider`` (the app-wide factory pattern, cf. the
        # Summarization dialog) — it was hardcoded to "ollama", so any rig
        # configured for another backend got connection-refused here.
        provider_name = str(s.get("summarisation.provider", "ollama") or "ollama").strip().lower()

        # V0.6.13: the llama.cpp-first local fallback (the operator's
        # follow-up report: "TRANSCRIBE SERVICE ... FIND[S] LLM ON OLLAMA
        # ONLY"). A live llama-server takes over the call — the factory's
        # llamacpp branch speaks OpenAI-compat to it and the DETECTED
        # served model wins over the dialog's model pick (the V0.4.30
        # precedent). Cloud selections are never probed; a dead llama.cpp
        # leaves this path byte-identical to V0.6.12.
        from core.llm.local_fallback import decide_llamacpp_first

        _lc = decide_llamacpp_first(s, provider_name)
        if _lc.note:
            log(f"  🦙 {_lc.note}", "INFO")
        if _lc.use_llamacpp:
            provider_name = "llamacpp"

        # V13.28.0: Create provider via the factory — gets supervisor + retry
        provider = create_provider(
            provider=provider_name,
            settings=s,
            log_callback=lambda msg, level="INFO": log(f"  [LLM] {msg}", level),
        )
        # V0.6.0 (T2): honor the caller's explicit endpoint on the Ollama
        # path — the factory pins the default localhost:11434, but this
        # service is always invoked with the endpoint the dialog resolved
        # from Settings, and the ``ollama_url`` parameter used to be dead.
        # (V0.6.13: skipped on the llama.cpp takeover — that provider reads
        # the llamacpp_* block, not the Ollama URL.)
        if provider_name == "ollama" and ollama_url:
            _base = str(ollama_url).rstrip("/")
            if _base and _base != "http://localhost:11434":
                provider.base_url = _base
        # Override model + timeout for this specific call (transcripts need 600s).
        # V0.6.13: on the llama.cpp takeover the DETECTED served model wins
        # over the dialog's pick.
        result = provider.complete_streaming(
            prompt=prompt,
            temperature=0.3,
            max_tokens=4096,
            model=_lc.model if _lc.use_llamacpp else model,
            on_chunk=None,  # no progress display during streaming
        )

        if not result or not result.strip():
            return "Error: LLM returned empty response."

        # Strip <think> tags (response_parser also does this, but do it here
        # for consistency with the old behavior)
        result = strip_thinking(result)
        # Strip code fences
        result = re.sub(r"^```(?:markdown)?\s*\n", "", result)
        result = re.sub(r"\n```\s*$", "", result)

        log(f"  ✅ Summary complete: {len(result)} chars", "INFO")
        return result.strip()

    except Exception as e:
        # V13.28.0: The provider handles Timeout/ConnectionError internally
        # with retry + supervisor. If we get here, all retries failed.
        err_type = type(e).__name__
        if "Timeout" in err_type or "timeout" in str(e).lower():
            return "Error: LLM request timed out after retries."
        if "Connection" in err_type or "connect" in str(e).lower():
            return "Error: Cannot connect to Ollama. Is it running? (ollama serve)"
        return f"Error: {e}"
