"""V0.6.55 (P5): the structured TranscribeError family.

WHY THIS MODULE EXISTS
──────────────────────
The transcribe pipeline's failure modes were AD-HOC until now: the
engines returned ``{"error": "…"}`` dicts, ``summarize_transcript``
returned ``"Error: …"`` STRINGS, and anything unexpected (the V0.6.53
NameError) bubbled up as a raw Python traceback that the dialog
rendered verbatim — the operator saw
``NameError: name '_transcript_text' is not defined`` instead of a
message a human can act on. The V0.6.54 CHANGELOG flagged the class:
"the pipeline's fragility (a single typo silently broke the whole
summarize path for one release) signals that the Step 4/5 LLM-call
path needs structural hardening."

THE CONTRACT
────────────
Every known failure mode of the pipeline raises (or carries) a
TranscribeError subclass with:
  - ``stage``  — WHERE it failed (audio-extraction / engine /
    transcription / summarize / pipeline);
  - ``message`` — the plain-language WHAT;
  - ``hint``   — the actionable FIX (default per class, overridable).

``str(err)`` is the ``user_message`` (stage + message + "Fix: …"), so
a dialog that just shows the exception already shows something a
non-programmer can act on. The dialog's worker catches TranscribeError
specifically; unexpected exceptions are wrapped as
``TranscribePipelineError`` with the original traceback in the log —
never a raw traceback to the face.
"""

from __future__ import annotations


class TranscribeError(Exception):
    """Base — a user-facing transcription-pipeline failure."""

    stage: str = "pipeline"
    hint: str = ""

    def __init__(self, message: str, *, stage: str | None = None, hint: str | None = None) -> None:
        self.message = message
        if stage is not None:
            self.stage = stage
        if hint is not None:
            self.hint = hint
        super().__init__(self.user_message)

    @property
    def user_message(self) -> str:
        parts = [f"[{self.stage}] {self.message}"]
        if self.hint:
            parts.append(f"Fix: {self.hint}")
        return "\n".join(parts)


class AudioExtractionError(TranscribeError):
    """ffmpeg could not extract/convert the audio (missing, failed, timed out)."""

    stage = "audio-extraction"
    hint = "Install ffmpeg and make sure it is on PATH, then try again."


class EngineNotFoundError(TranscribeError):
    """The transcription engine's binary or model file is missing."""

    stage = "engine"
    hint = "Check the engine paths in the Transcribe Service dialog (the 📁 buttons)."


class TranscriptionEngineError(TranscribeError):
    """The transcription engine ran but failed (non-zero exit, timeout)."""

    stage = "transcription"


class EmptyTranscriptError(TranscribeError):
    """The engine succeeded but produced zero transcript text."""

    stage = "transcription"
    hint = "Check the raw CLI output file next to the input; the audio may be silent or unreadable."


class LLMConnectionError(TranscribeError):
    """The LLM backend could not be reached / timed out after retries."""

    stage = "summarize"
    hint = "Start your LLM (llama-server or `ollama serve`) and use the 🔌 Test button to verify."


class LLMEmptyResponseError(TranscribeError):
    """The LLM connected but returned an empty response."""

    stage = "summarize"
    hint = "Retry; if it persists, the model may be too small for the prompt — try a larger model."


class LLMGenerationError(TranscribeError):
    """The LLM call failed in an unexpected way (transport, parsing)."""

    stage = "summarize"
    hint = "Check the LLM backend logs; the \U0001f50c Test button verifies connectivity and generation speed."


class TranscribePipelineError(TranscribeError):
    """An unexpected exception inside the pipeline (the V0.6.53
    NameError class of failure) — wrapped with stage context so the
    dialog never shows a bare traceback. The original error is
    preserved as ``__cause__`` for the log."""

    stage = "pipeline"
    hint = "This is an unexpected internal error — check the log for the original traceback and report it."
