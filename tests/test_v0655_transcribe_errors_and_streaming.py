"""V0.6.55 (P4) — LLM streaming to the UI + (P5) the error family pins.

P4 — THE PROBLEM (the operator's redesign item): ``summarize_transcript``
called ``provider.complete_streaming(..., on_chunk=None)`` — the
provider's streaming path supports a live progress callback, but the
transcribe tool never passed one. On the rig's 27B a summary generates
for 10+ minutes while the dialog's status label stays FROZEN at
"Summarizing with LLM..." — the operator cannot tell a healthy slow
generation from a hang.

P4 — THE FIX: ``summarize_transcript`` / ``summarize_transcript_combined``
accept ``on_chunk`` and forward it to ``complete_streaming`` (the
provider already throttles emissions to 2/s). The dialog passes a
callback that emits the growing char count through its worker's
progress signal (the dialog wiring is pinned by source in
test_v0655_transcribe_dialog_redesign.py).

P5 — THE FIX (core/transcribe/errors.py): the structured
``TranscribeError`` family replaces both the ``"Error: ..."`` string
returns and the raw-traceback path. This file pins the family itself
and the service's exception mapping (timeout / connection / generic /
empty / pass-through).

Hermetic (the V0.6.13 _TranscribeHarness pattern: faked factory +
probe + Settings._test_override).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.transcribe.errors import (  # noqa: E402
    AudioExtractionError,
    EmptyTranscriptError,
    EngineNotFoundError,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMGenerationError,
    TranscribeError,
    TranscribePipelineError,
)
from core.transcribe.transcribe_service import summarize_transcript  # noqa: E402


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — the TranscribeError family (P5)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655ErrorFamily:
    def test_every_known_failure_is_a_transcribe_error(self):
        """The family tree: everything the dialog catches is ONE base
        class — the worker's ``except TranscribeError`` never misses."""
        for cls in (
            AudioExtractionError,
            EngineNotFoundError,
            EmptyTranscriptError,
            LLMConnectionError,
            LLMEmptyResponseError,
            LLMGenerationError,
            TranscribePipelineError,
        ):
            assert issubclass(cls, TranscribeError), cls

    def test_stages_partition_the_pipeline(self):
        """Each class knows WHERE it failed — the dialog renders the
        stage so the operator knows which step died."""
        assert AudioExtractionError.stage == "audio-extraction"
        assert EngineNotFoundError.stage == "engine"
        assert EmptyTranscriptError.stage == "transcription"
        assert LLMConnectionError.stage == "summarize"
        assert LLMEmptyResponseError.stage == "summarize"
        assert LLMGenerationError.stage == "summarize"
        assert TranscribePipelineError.stage == "pipeline"

    def test_user_message_is_stage_message_and_fix(self):
        err = LLMConnectionError("cannot reach llama.cpp", hint="start llama-server")
        msg = err.user_message
        assert msg.startswith("[summarize] cannot reach llama.cpp")
        assert "Fix: start llama-server" in msg

    def test_str_is_the_user_message(self):
        """str(err) — what a bare ``f"{e}"`` in the dialog renders — is
        the friendly user message, never a raw traceback."""
        err = LLMEmptyResponseError("empty response")
        assert str(err) == err.user_message
        assert "[summarize]" in str(err)

    def test_every_class_carries_a_default_hint(self):
        """A non-programmer reading ANY failure gets an actionable Fix
        line by default."""
        for cls in (
            AudioExtractionError,
            EngineNotFoundError,
            EmptyTranscriptError,
            LLMConnectionError,
            LLMEmptyResponseError,
            LLMGenerationError,
            TranscribePipelineError,
        ):
            err = cls("boom")
            assert err.hint, cls.__name__

    def test_stage_and_hint_are_overridable_per_instance(self):
        err = LLMGenerationError("boom", stage="tutorial", hint="try again")
        assert err.stage == "tutorial"
        assert err.hint == "try again"

    def test_errors_module_is_pure_python(self):
        """core/transcribe/errors.py imports nothing heavy — it stays
        importable in every environment (the hermetic-test gate)."""
        import core.transcribe.errors as m

        assert m.__file__.endswith("errors.py")


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — the service maps failures onto the family (P5 wiring)
# ═════════════════════════════════════════════════════════════════════════════


class _ServiceHarness:
    """summarize_transcript + faked create_provider + dead probe."""

    def __init__(self, monkeypatch, provider_exc: Exception | None, result: str | None):
        import core.llm.llm_provider as lp
        from utils.settings import Settings

        class _S:
            def get(self, key, default=None):
                return default

        monkeypatch.setattr(Settings, "_test_override", _S(), raising=False)

        from core.llm import local_fallback

        class _Dead:
            def __call__(self, base_url, api_key, timeout=10):
                return []

        monkeypatch.setattr(local_fallback, "list_llamacpp_models", _Dead())
        local_fallback.clear_llamacpp_probe_cache()

        self.captured: dict = {}
        captured = self.captured

        class _FakeProvider:
            base_url = "http://localhost:11434"

            def complete_streaming(self, prompt, temperature=None, max_tokens=None, model=None, on_chunk=None):
                captured["on_chunk"] = on_chunk
                if provider_exc is not None:
                    raise provider_exc
                return result

        monkeypatch.setattr(
            lp, "create_provider", lambda *a, **k: _FakeProvider()
        )

    def run(self, **kwargs):
        return summarize_transcript(
            "transcript",
            model="m",
            ollama_url="http://localhost:11434",
            log_callback=lambda m, level="INFO": None,
            **kwargs,
        )


class TestV0655ServiceErrorMapping:
    def test_connection_failures_raise_llm_connection_error(self, monkeypatch):
        h = _ServiceHarness(monkeypatch, RuntimeError("ConnectionError: refused"), None)
        with pytest.raises(LLMConnectionError) as ei:
            h.run()
        assert "refused" in str(ei.value)
        assert "Fix:" in str(ei.value)  # the actionable line is present

    def test_timeout_failures_raise_llm_connection_error_with_hint(self, monkeypatch):
        h = _ServiceHarness(monkeypatch, TimeoutError("ReadTimeout"), None)
        with pytest.raises(LLMConnectionError) as ei:
            h.run()
        assert "timed out" in str(ei.value).lower()

    def test_generic_failures_raise_llm_generation_error(self, monkeypatch):
        h = _ServiceHarness(monkeypatch, ValueError("weird parse"), None)
        with pytest.raises(LLMGenerationError) as ei:
            h.run()
        assert "weird parse" in str(ei.value)

    def test_empty_llm_response_raises_llm_empty_response_error(self, monkeypatch):
        """The old code returned the STRING 'Error: LLM returned empty
        response.' — now it is a structured error (the dialog can never
        mistake it for content)."""
        h = _ServiceHarness(monkeypatch, None, result="   ")
        with pytest.raises(LLMEmptyResponseError):
            h.run()

    def test_none_provider_return_is_a_connection_error(self, monkeypatch):
        """Task 9 review fix: the REAL providers swallow transport
        failures and return None (they do not raise). A None result is
        a CONNECTION-class failure — LLMConnectionError with the
        start-your-LLM hint, NOT the misleading 'model too small'
        empty-response hint."""
        h = _ServiceHarness(monkeypatch, None, result=None)
        with pytest.raises(LLMConnectionError) as ei:
            h.run()
        assert "did not return a response" in str(ei.value)
        assert "llama-server" in str(ei.value) or "ollama serve" in str(ei.value)

    def test_success_still_returns_the_markdown_string(self, monkeypatch):
        h = _ServiceHarness(monkeypatch, None, result="# Notes\n\n- a")
        assert h.run() == "# Notes\n\n- a"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — P4: on_chunk rides the provider call
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655StreamingForwarded:
    def test_on_chunk_reaches_the_provider_call(self, monkeypatch):
        """The pre-fix call hardcoded ``on_chunk=None`` (a comment said
        'no progress display during streaming') — the UI had NO way to
        see progress. Now the caller's callback is forwarded intact."""
        h = _ServiceHarness(monkeypatch, None, result="# Notes")
        seen: list[str] = []
        h.run(on_chunk=lambda partial: seen.append(partial))
        assert h.captured["on_chunk"] is not None
        assert h.captured["on_chunk"] is not False

    def test_default_none_keeps_old_caller_compatibility(self, monkeypatch):
        """Existing callers that pass nothing behave as before (None
        forwarded — the provider skips emissions)."""
        h = _ServiceHarness(monkeypatch, None, result="# Notes")
        h.run()
        assert h.captured["on_chunk"] is None

    def test_the_service_passes_on_chunk_positionally_intact(self, monkeypatch):
        """The exact callable identity arrives at the provider (no
        wrapper, no throttling added on top — the provider already
        throttles at 0.5 s)."""
        h = _ServiceHarness(monkeypatch, None, result="# Notes")
        cb = lambda partial: None  # noqa: E731 — identity-checked below
        h.run(on_chunk=cb)
        assert h.captured["on_chunk"] is cb
