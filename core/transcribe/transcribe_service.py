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
import re
import subprocess
import sys
from pathlib import Path

from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from core.system.timeouts import LONG_RUN_TIMEOUT_S
from core.transcribe.errors import (
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMGenerationError,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# V0.6.55 (P2): the transcript PROMPT budget — replaces the silent
# ``transcript[:8000]`` amputation. 24k prompt tokens + 12k output cap +
# 512 margin fits the default 65k llama.cpp window with room to spare;
# a 15-min video (~20k chars ≈ 5k tokens) passes WHOLE. Only an absurd
# wall (3h+ lecture) trips the cut — and then it is a LOUD,
# sentence-boundary cut with an explicit marker (see
# fit_transcript_to_budget).
# ═══════════════════════════════════════════════════════════════════════
TRANSCRIPT_PROMPT_TOKEN_BUDGET = 24_000

# Task 9 review fix: the truncation marker's own tokens are RESERVED in
# the fit search — the old code cut the body to exactly the budget and
# then appended the ~150-char marker ON TOP of it (24,036 tokens for a
# 24,000 budget — measured by the fresh-eyes review). A 64-token
# reserve comfortably covers the marker at any realistic count.
_TRANSCRIPT_MARKER_TOKEN_RESERVE = 64

# The truncation marker appended when the budget trips (the model AND
# the operator both get to see that the tail was dropped).
_TRANSCRIPT_MARKER_LABEL = "[... transcript truncated"

# V0.6.55 (P3): the combined-output split marker. The prompt instructs
# the model to emit EXACTLY ``<<<ELIXIR-TRANSCRIBE-SPLIT>>>`` between
# the notes document and the tutorial document; the splitter tolerates
# the predictable drift (case, 1-6 angle brackets, underscores/hyphens/
# spaces, a stray code fence around it) and prefers a marker that
# stands on its OWN line (the contract line) over an inline mention
# inside a sentence (body text).
_MARKER_CORE = r"ELIXIR[-_ ]?TRANSCRIBE[-_ ]?SPLIT"
_COMBINED_SPLIT_OWN_LINE_RE = re.compile(
    rf"^[ \t]*<{{1,6}}\s*{_MARKER_CORE}\s*>{{1,6}}[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_COMBINED_SPLIT_ANYWHERE_RE = re.compile(
    rf"<{{1,6}}\s*{_MARKER_CORE}\s*>{{1,6}}",
    re.IGNORECASE,
)


def _count_prompt_tokens(text: str) -> int:
    """Best-available token count for the budget math.

    Deferred import: core.llm.context_budget → utils.token_counter →
    tiktoken (with a words*4//3 fallback when tiktoken is absent — the
    hermetic-test gate). Never raises.
    """
    try:
        from core.llm.context_budget import count_tokens

        return int(count_tokens(text))
    except Exception:
        return max(1, len(text.split()) * 4 // 3)


def fit_transcript_to_budget(transcript: str, max_tokens: int | None = None) -> dict:
    """V0.6.55 (P2): fit the transcript into the LLM prompt budget.

    - Fits (the 15-min-video case) → the FULL text, ``truncated`` False.
    - Over budget → the cut lands on a sentence/paragraph boundary
      (word boundary as the last resort — a punctuation-free AND
      whitespace-free wall in the 400-char snap window can still
      hard-cut, the honest boundary of the heuristic), and an explicit
      marker naming the used/total counts is appended so the cut is
      visible to the model and the operator. The marker's tokens are
      RESERVED in the fit search (body + marker never exceed the
      budget).

    Returns ``{"text": str, "truncated": bool, "chars_used": int,
    "chars_total": int}`` — never raises (empty input is a valid,
    untruncated empty fit).
    """
    text = transcript or ""
    total_chars = len(text)
    budget = int(max_tokens) if max_tokens else TRANSCRIPT_PROMPT_TOKEN_BUDGET
    if budget <= 0 or not text:
        return {
            "text": text,
            "truncated": False,
            "chars_used": total_chars,
            "chars_total": total_chars,
        }
    if _count_prompt_tokens(text) <= budget:
        return {
            "text": text,
            "truncated": False,
            "chars_used": total_chars,
            "chars_total": total_chars,
        }

    # Task 9 review fix: the fit search targets the budget MINUS the
    # marker's own tokens, so body + marker never exceeds the budget.
    body_budget = max(1, budget - _TRANSCRIPT_MARKER_TOKEN_RESERVE)

    # Over budget: find the largest prefix whose token count fits.
    # Binary search on the char cut (each probe is a token count — the
    # token-counter cache does not help across probes, but log2(n)
    # probes of an O(n) count is fine for a one-shot pipeline step).
    lo, hi = 0, total_chars  # lo fits, hi does not (hi == total over)
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if _count_prompt_tokens(text[:mid]) <= body_budget:
            lo = mid
        else:
            hi = mid
    cut = lo

    # Snap the cut BACK to a sentence boundary (or a word boundary as
    # the last resort) — never mid-word.
    window = text[max(0, cut - 400) : cut]
    best = -1
    for punct in (". ", ".\n", "! ", "? ", "\n\n"):
        idx = window.rfind(punct)
        if idx > best:
            best = idx
    if best >= 0:
        cut = max(0, cut - 400) + best + 1
    else:
        # no sentence boundary in the window — fall back to whitespace
        ws = window.rfind(" ")
        if ws >= 0:
            cut = max(0, cut - 400) + ws

    body = text[:cut].rstrip()
    used = len(body)
    marker = (
        f"\n\n{_TRANSCRIPT_MARKER_LABEL}: {used:,} of {total_chars:,} characters "
        f"were passed to the model — the remaining tail was cut at the "
        f"context budget to fit the prompt ...]"
    )
    return {
        "text": body + marker,
        "truncated": True,
        "chars_used": used,
        "chars_total": total_chars,
    }


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
    on_chunk=None,
    prompt_token_budget: int | None = None,
) -> str:
    """Summarize transcript into Obsidian-friendly markdown using the LLM.

    V13.28.0 (P2.10): delegates to ``llm_provider.create_provider()`` +
    ``complete_streaming()`` -- supervisor crash recovery, retry with
    backoff, proxy-proof HTTP, thinking-block stripping.

    V0.6.55 (the transcribe-tool redesign):
    - P2: the prompt is rendered with ``fit_transcript_to_budget`` --
      the WHOLE transcript reaches the LLM when it fits (the old
      ``[:8000]`` slice amputated ~half of a 15-min video's text);
      an over-budget wall gets a LOUD sentence-boundary cut + marker.
    - P4: ``on_chunk`` is forwarded to the provider's streaming path
      so the UI can show the generation growing (a frozen status
      label for 10+ minutes was the rig's reported symptom).
    - P5: failures RAISE the structured ``TranscribeError`` family
      (LLMConnectionError / LLMEmptyResponseError /
      LLMGenerationError) instead of returning ``"Error: ..."`` strings --
      the dialog renders ``str(err)`` (stage + message + fix).

    Returns the summarized markdown. Raises TranscribeError subclasses.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    fitted = fit_transcript_to_budget(transcript, max_tokens=prompt_token_budget)
    if fitted["truncated"]:
        log(
            f"  \u26a0\ufe0f Transcript truncated for the prompt budget: "
            f"{fitted['chars_used']:,} of {fitted['chars_total']:,} chars kept "
            f"(the cut is marked in the prompt).",
            "WARNING",
        )

    from core.summarisation.prompt_manager import PromptManager

    _pm = PromptManager()
    # V0.6.43: select the prompt template based on output_type.
    if output_type == "tutorial":
        prompt = _pm.render_template(
            "transcribe/transcript_tutorial",
            transcript=fitted["text"],
        )
        log("  Generating tutorial/educational guide...", "INFO")
        progress(92, "Generating tutorial guide with LLM...")
    else:
        prompt = _pm.render_template(
            "transcribe/transcript_notes",
            transcript=fitted["text"],
        )
        log("  Summarizing transcript (core concepts + key takeaways)...", "INFO")
        progress(92, "Summarizing with LLM...")

    result = _complete_transcribe_prompt(
        prompt=prompt,
        model=model,
        ollama_url=ollama_url,
        log=log,
        on_chunk=on_chunk,
    )
    log(f"  \u2705 Summary complete: {len(result)} chars", "INFO")
    return result


def summarize_transcript_combined(
    transcript: str,
    model: str = RIG_FALLBACK_MODEL,
    ollama_url: str = "http://localhost:11434",
    log_callback=None,
    progress_callback=None,
    on_chunk=None,
    prompt_token_budget: int | None = None,
) -> dict:
    """V0.6.55 (P3): BOTH outputs -- notes AND tutorial -- in ONE LLM round trip.

    The two-output flow used to run two sequential full generations on
    the same transcript (2x the wall-clock on a dense 27B at 2-6 tok/s
    -- the rig's reported 10+ minute waits). The combined prompt
    (``transcribe/transcript_combined``) asks the model to emit both
    documents separated by ``<<<ELIXIR-TRANSCRIBE-SPLIT>>>``; the
    response is split with ``split_combined_output``.

    Returns ``{"summary": str, "tutorial": str | None, "split_ok":
    bool, "combined": True}`` -- on ``split_ok`` False the RAW response
    is returned as ``summary`` with ``tutorial=None`` and the CALLER
    falls back to a separate tutorial call (correctness is never
    sacrificed to save a round trip). Raises TranscribeError subclasses
    on LLM failures (same contract as ``summarize_transcript``).
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    fitted = fit_transcript_to_budget(transcript, max_tokens=prompt_token_budget)
    if fitted["truncated"]:
        log(
            f"  \u26a0\ufe0f Transcript truncated for the prompt budget: "
            f"{fitted['chars_used']:,} of {fitted['chars_total']:,} chars kept.",
            "WARNING",
        )

    from core.summarisation.prompt_manager import PromptManager

    _pm = PromptManager()
    prompt = _pm.render_template(
        "transcribe/transcript_combined",
        transcript=fitted["text"],
    )
    log("  Generating combined notes + tutorial (one LLM call)...", "INFO")
    progress(92, "Summarizing with LLM (notes + tutorial in one call)...")

    raw = _complete_transcribe_prompt(
        prompt=prompt,
        model=model,
        ollama_url=ollama_url,
        log=log,
        on_chunk=on_chunk,
    )
    parts = split_combined_output(raw)
    if parts["ok"]:
        log(
            "  \u2705 Combined output split cleanly "
            f"(notes {len(parts['summary'])} chars, tutorial {len(parts['tutorial'])} chars)",
            "INFO",
        )
        return {
            "summary": parts["summary"],
            "tutorial": parts["tutorial"],
            "split_ok": True,
            "combined": True,
        }
    log(
        "  \u26a0\ufe0f Combined output did not contain the split marker -- "
        "falling back to a separate tutorial call.",
        "WARNING",
    )
    return {
        "summary": raw,
        "tutorial": None,
        "split_ok": False,
        "combined": True,
    }


def split_combined_output(text: str) -> dict:
    """V0.6.55 (P3): split a combined notes+tutorial response on the marker.

    Tolerates the predictable model drift: case, extra angle brackets,
    underscores/hyphens/spaces inside the marker name, and a stray code
    fence wrapping either document. ``{"ok": bool, "summary": str | None,
    "tutorial": str | None}`` -- ok requires BOTH sides non-empty.
    """
    if not text or not text.strip():
        return {"ok": False, "summary": None, "tutorial": None}
    # Prefer a marker on its OWN line (the contract line); an inline
    # mention inside a sentence is body text, not the split.
    match = _COMBINED_SPLIT_OWN_LINE_RE.search(text) or _COMBINED_SPLIT_ANYWHERE_RE.search(text)
    if not match:
        return {"ok": False, "summary": None, "tutorial": None}

    def _strip_fences(s: str) -> str:
        s = re.sub(r"^```(?:markdown|md)?\s*\n", "", s.strip())
        s = re.sub(r"\n```\s*$", "", s)
        return s.strip()

    summary = _strip_fences(text[: match.start()])
    tutorial = _strip_fences(text[match.end() :])
    return {
        "ok": bool(summary) and bool(tutorial),
        "summary": summary or None,
        "tutorial": tutorial or None,
    }


def _complete_transcribe_prompt(
    prompt: str,
    model: str,
    ollama_url: str,
    log,
    on_chunk=None,
) -> str:
    """The shared LLM-call seam for BOTH ``summarize_transcript`` and
    ``summarize_transcript_combined``: routing (the V0.6.13
    llama.cpp-first policy + the V0.6.55 port auto-detection via the
    factory), the provider call with streaming (P4), and the V0.6.55
    structured-error mapping (P5). Returns the cleaned markdown;
    raises LLMConnectionError / LLMEmptyResponseError /
    LLMGenerationError.
    """
    from core.summarisation.response_parser import strip_thinking

    log(f"  \U0001f4dd Summarizing with {model}...", "INFO")

    try:
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings

        s = Settings()
        # V0.6.0 (T2): provider follows the configured
        # ``summarisation.provider`` (the app-wide factory pattern).
        provider_name = str(s.get("summarisation.provider", "ollama") or "ollama").strip().lower()

        # V0.6.13: the llama.cpp-first local fallback -- a live
        # llama-server takes over the call (the factory's llamacpp
        # branch speaks OpenAI-compat to it; the DETECTED served model
        # wins over the dialog's model pick -- the V0.4.30 precedent).
        # V0.6.55 (P1a): the factory resolves the base URL through the
        # port auto-detector, so the takeover works when llama-server
        # lives on :8000 (the rig) without any manual settings edit.
        from core.llm.local_fallback import decide_llamacpp_first

        _lc = decide_llamacpp_first(s, provider_name)
        if _lc.note:
            log(f"  \U0001f999 {_lc.note}", "INFO")
        if _lc.use_llamacpp:
            provider_name = "llamacpp"

        # V13.28.0: the factory -- supervisor + retry for free.
        provider = create_provider(
            provider=provider_name,
            settings=s,
            log_callback=lambda msg, level="INFO": log(f"  [LLM] {msg}", level),
        )
        # V0.6.0 (T2): honor the caller's explicit endpoint on the Ollama
        # path (the factory pins the default localhost:11434, but this
        # service is always invoked with the dialog-resolved endpoint).
        if provider_name == "ollama" and ollama_url:
            _base = str(ollama_url).rstrip("/")
            if _base and _base != "http://localhost:11434":
                provider.base_url = _base
        # V0.6.55 (P4): the caller's on_chunk rides the streaming call --
        # the UI shows the generation growing instead of a frozen label.
        result = provider.complete_streaming(
            prompt=prompt,
            temperature=0.3,
            max_tokens=4096,
            model=_lc.model if _lc.use_llamacpp else model,
            on_chunk=on_chunk,
        )

        # Task 9 review fix: the REAL providers (LlamaCppProvider /
        # OllamaProvider) swallow their transport failures and return
        # None after the retry policy gives up -- they do not raise.
        # A None result is therefore a CONNECTION-CLASS failure (the
        # backend is down / unreachable), NOT an empty generation; the
        # old fall-through reported it as LLMEmptyResponseError with
        # the misleading "model too small" hint.
        if result is None:
            raise LLMConnectionError(
                "The LLM backend did not return a response after retries "
                "(the provider gave up -- the backend is likely down or "
                "unreachable).",
                hint=(
                    "Start your LLM (llama-server or `ollama serve`) and "
                    "verify with the \U0001f50c Test button."
                ),
            )

        if not result or not result.strip():
            raise LLMEmptyResponseError(
                "The LLM returned an empty response for the transcript summary."
            )

        # Strip <think> blocks + code fences (both public callers get the
        # same cleaning).
        result = strip_thinking(result)
        result = re.sub(r"^```(?:markdown|md)?\s*\n", "", result)
        result = re.sub(r"\n```\s*$", "", result)
        return result.strip()

    except (LLMConnectionError, LLMEmptyResponseError, LLMGenerationError):
        raise  # P5: structured errors pass through untouched
    except Exception as e:
        # V13.28.0: the provider handles Timeout/ConnectionError
        # internally with retry + supervisor; landing here means all
        # retries failed -- map to the structured family (P5).
        err_type = type(e).__name__
        if "Timeout" in err_type or "timeout" in str(e).lower():
            raise LLMConnectionError(
                "LLM request timed out after retries.",
                hint=(
                    "Check with the \U0001f50c Test button -- a very slow "
                    "generation (CPU fallback) can also trip the timeout."
                ),
            ) from e
        if "Connection" in err_type or "connect" in str(e).lower():
            raise LLMConnectionError(
                f"Cannot connect to the LLM backend ({e}).",
            ) from e
        raise LLMGenerationError(f"LLM call failed: {e}") from e
