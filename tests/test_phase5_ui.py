"""V18.2.26 (Phase 5.1 + 5.2) — Tests for progress model + error remediation.

Covers:
- ProgressEvent construction + to_legacy + to_dict
- ProgressEmitter.emit_stage + mark_chapter_complete
- ProgressEmitter calls legacy + structured callbacks
- get_error_remediation maps each exception class correctly
- format_for_log produces a single-line message
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.obs.error_remediation import (
    RemediationInfo,
    format_for_log,
    get_error_remediation,
)
from core.obs.progress import (
    STAGE_CHAPTER_COMPLETE,
    STAGE_CONTENT_JUDGE,
    STAGE_PRIMARY_SUMMARY,
    ProgressEmitter,
    ProgressEvent,
)


class TestProgressEvent:
    def test_construction(self):
        e = ProgressEvent(
            stage=STAGE_PRIMARY_SUMMARY,
            chapter=3,
            chapter_total=12,
            pct=0.5,
            overall_pct=0.25,
            message="Summarizing chapter 3",
        )
        assert e.stage == STAGE_PRIMARY_SUMMARY
        assert e.chapter == 3
        assert e.pct == 0.5

    def test_to_legacy(self):
        e = ProgressEvent(
            stage="test_stage",
            overall_pct=0.42,
            message="Halfway there",
        )
        frac, msg = e.to_legacy()
        assert frac == 0.42
        assert msg == "Halfway there"

    def test_to_legacy_falls_back_to_stage(self):
        e = ProgressEvent(stage="my_stage", overall_pct=0.5)
        frac, msg = e.to_legacy()
        assert msg == "my_stage"  # falls back to stage when message empty

    def test_to_dict(self):
        e = ProgressEvent(
            stage="test",
            chapter=2,
            chapter_total=10,
            pct=0.3,
            overall_pct=0.2,
            message="msg",
            elapsed_sec=12.5,
        )
        d = e.to_dict()
        assert d["stage"] == "test"
        assert d["chapter"] == 2
        assert d["pct"] == 0.3
        assert d["elapsed_sec"] == 12.5


class TestProgressEmitter:
    def test_emit_calls_legacy_callback(self):
        legacy = MagicMock()
        emitter = ProgressEmitter(progress_callback=legacy, total_chapters=4)
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=1, pct=0.0)
        assert legacy.call_count >= 1
        frac, msg = legacy.call_args[0]
        assert 0.0 <= frac <= 1.0

    def test_emit_calls_stage_callback(self):
        stage_cb = MagicMock()
        emitter = ProgressEmitter(stage_callback=stage_cb, total_chapters=4)
        event = emitter.emit_stage(STAGE_CONTENT_JUDGE, chapter=2, pct=0.5)
        stage_cb.assert_called_once_with(event)

    def test_overall_pct_advances_with_chapters(self):
        emitter = ProgressEmitter(total_chapters=4)
        # Chapter 1, primary summary at 50%
        e1 = emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=1, pct=0.5)
        # Chapter 1 complete
        emitter.mark_chapter_complete(1)
        # Chapter 2, primary summary at 0%
        e2 = emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=2, pct=0.0)
        assert e2.overall_pct > e1.overall_pct

    def test_mark_chapter_complete(self):
        emitter = ProgressEmitter(total_chapters=3)
        event = emitter.mark_chapter_complete(2)
        assert event.stage == STAGE_CHAPTER_COMPLETE
        assert event.chapter == 2
        assert event.pct == 1.0

    def test_legacy_callback_exception_swallowed(self):
        """If the legacy callback raises, emit must not crash."""
        def bad_callback(frac, msg):
            raise RuntimeError("callback crashed")
        emitter = ProgressEmitter(progress_callback=bad_callback, total_chapters=2)
        # Should not raise
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=1, pct=0.5)

    def test_stage_callback_exception_swallowed(self):
        """If the stage callback raises, emit must not crash."""
        def bad_stage_cb(event):
            raise RuntimeError("stage cb crashed")
        emitter = ProgressEmitter(stage_callback=bad_stage_cb, total_chapters=2)
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=1, pct=0.5)

    def test_summary_string(self):
        emitter = ProgressEmitter(total_chapters=5)
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=2, pct=0.5)
        s = emitter.summary()
        assert "2/5" in s or "completed" in s.lower()

    def test_total_chapters_minimum_1(self):
        """Avoid div-by-zero when total_chapters=0."""
        emitter = ProgressEmitter(total_chapters=0)
        assert emitter.total_chapters == 1


class TestErrorRemediation:
    def _make_exc(self, exc_class_name: str, msg: str = "", **attrs):
        """Create a mock exception with the given class name."""
        exc = Exception(msg)
        exc.__class__.__name__ = exc_class_name
        for k, v in attrs.items():
            setattr(exc, k, v)
        return exc

    def test_model_not_found_404(self):
        from core.llm.retry import ModelNotFound404Error
        exc = ModelNotFound404Error(model="gemma4-12b:latest", detail="not found")
        r = get_error_remediation(exc)
        assert r.severity == "error"
        assert r.title == "Model not installed"
        assert "gemma4-12b:latest" in r.action
        assert r.action_type == "command"

    def test_ollama_timeout(self):
        from core.llm.retry import OllamaTimeoutError
        exc = OllamaTimeoutError(model="test", timeout=300, original=None)
        r = get_error_remediation(exc)
        assert r.severity == "warning"
        assert r.title == "Model stalled"
        assert "IQ2_M" in r.action

    def test_ollama_oom(self):
        from core.llm.retry import OllamaOOMError
        exc = OllamaOOMError(model="gemma4-12b:latest", num_ctx=32768, detail="CUDA out of memory")
        r = get_error_remediation(exc)
        assert r.severity == "error"
        assert r.title == "Out of GPU memory"
        assert "max_context_tokens" in r.action

    def test_embedder_unavailable(self):
        from core.llm.embedder_backend import EmbedderUnavailable
        exc = EmbedderUnavailable("model 'all-MiniLM-L6-v2' is unhealthy")
        r = get_error_remediation(exc)
        assert r.severity == "warning"
        assert r.title == "Embedding model unavailable"
        assert "ollama pull" in r.action

    def test_connection_error(self):
        exc = ConnectionError("Connection refused to localhost:11434")
        r = get_error_remediation(exc)
        assert r.severity == "error"
        assert r.title == "Can't reach Ollama"
        assert "ollama serve" in r.action.lower() or "Ollama" in r.action

    def test_timeout_exception(self):
        import requests
        exc = requests.exceptions.Timeout("read timeout=600")
        r = get_error_remediation(exc)
        assert r.title == "Request timed out"
        assert r.action_type == "settings"

    def test_empty_response(self):
        exc = RuntimeError("empty response from model")
        r = get_error_remediation(exc)
        assert r.title == "Model returned empty response"
        assert "temperature" in r.action.lower() or "IQ2_M" in r.action

    def test_fallback_unknown_exception(self):
        exc = ValueError("something unexpected")
        r = get_error_remediation(exc)
        assert r.severity == "error"
        assert r.title == "Unexpected error"
        assert "ValueError" in r.technical

    def test_format_for_log(self):
        r = RemediationInfo(
            severity="error",
            title="Model not installed",
            message="The model is missing.",
            action="ollama pull gemma4-12b:latest",
            technical="ModelNotFound404Error: model not found",
        )
        line = format_for_log(r)
        assert "[ERROR]" in line
        assert "Model not installed" in line
        assert "ollama pull" in line
        assert "ModelNotFound404Error" in line


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
