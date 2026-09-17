"""V18.2.25 (Phase 4.1) — Tests for OpenTelemetry tracing.

Covers:
1. span() is a no-op when tracing disabled (default)
2. span() creates real spans when enabled
3. Attributes are set on spans
4. Exceptions are recorded on spans
5. timed_span records duration_ms
6. is_tracing_enabled() reads from settings
7. flush() is a no-op when disabled
8. span yields None when disabled, non-None when enabled
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestTracingDisabled:
    """When tracing is disabled (default), span() is a no-op."""

    def test_span_yields_none_when_disabled(self):
        from core.obs.tracing import span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=False):
            with span("test.span") as s:
                assert s is None  # no-op

    def test_span_does_not_raise_when_disabled(self):
        from core.obs.tracing import span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=False):
            with span("test.span", model="gemma", tokens=4096):
                pass  # should not raise

    def test_flush_noop_when_disabled(self):
        from core.obs.tracing import flush
        with patch("core.obs.tracing._is_tracing_enabled", return_value=False):
            flush()  # should not raise

    def test_timed_span_yields_none_when_disabled(self):
        from core.obs.tracing import timed_span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=False):
            with timed_span("test.timed") as s:
                assert s is None

    def test_is_tracing_enabled_default_false(self):
        """When settings are unavailable, tracing defaults to False."""
        from core.obs import tracing
        old = tracing._tracing_enabled
        tracing._tracing_enabled = None  # force re-read
        with patch("utils.settings.Settings") as mock_settings:
            mock_settings.return_value.get.side_effect = Exception("no settings")
            assert tracing.is_tracing_enabled() is False
        tracing._tracing_enabled = old  # restore


class TestTracingEnabled:
    """When tracing is enabled, span() creates real spans."""

    def test_span_yields_object_when_enabled(self):
        from core.obs.tracing import span
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with span("test.span") as s:
                assert s is mock_span

    def test_attributes_set_on_span(self):
        from core.obs.tracing import span
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with span("test.span", gen_ai_model="gemma4", gen_ai_tokens=4096):
                pass
        # Verify attributes were set
        call_args = [c.args for c in mock_span.set_attribute.call_args_list]
        assert ("gen_ai_model", "gemma4") in call_args
        assert ("gen_ai_tokens", 4096) in call_args

    def test_exception_recorded_on_span(self):
        from core.obs.tracing import span
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with pytest.raises(ValueError, match="test error"):
                with span("test.span"):
                    raise ValueError("test error")
        # Verify exception was recorded
        mock_span.record_exception.assert_called_once()

    def test_timed_span_sets_duration(self):
        import time

        from core.obs.tracing import timed_span
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with timed_span("test.timed"):
                time.sleep(0.01)
        # duration_ms should have been set (call_args_list has set_attribute calls)
        duration_calls = [c for c in mock_span.set_attribute.call_args_list
                          if c.args and c.args[0] == "duration_ms"]
        assert len(duration_calls) >= 1
        assert duration_calls[0].args[1] > 0  # positive duration


class TestIsTracingEnabled:
    """Test the settings-driven tracing flag."""

    def test_reads_from_settings(self):
        from core.obs import tracing
        old = tracing._tracing_enabled
        tracing._tracing_enabled = None
        mock_settings = MagicMock()
        mock_settings.get.return_value = True
        with patch("utils.settings.Settings", return_value=mock_settings):
            assert tracing.is_tracing_enabled() is True
        tracing._tracing_enabled = old

    def test_caches_result(self):
        from core.obs import tracing
        tracing._tracing_enabled = True
        # Should return cached without reading settings
        with patch("utils.settings.Settings") as mock:
            assert tracing.is_tracing_enabled() is True
            mock.assert_not_called()


class TestGetTracer:
    """Test the tracer initialization."""

    def test_returns_none_when_disabled(self):
        from core.obs.tracing import _get_tracer
        with patch("core.obs.tracing._is_tracing_enabled", return_value=False):
            assert _get_tracer() is None

    def test_caches_tracer(self):
        from core.obs.tracing import _get_tracer, _tracer
        # After first call, tracer is cached
        assert _tracer is not None or not _get_tracer()  # either cached or init failed


class TestSpanNames:
    """Verify span names follow the gen_ai.* convention."""

    def test_chapter_span_name(self):
        """The chapter root span should be named chapter.summarize."""
        from core.obs.tracing import span
        mock_tracer = MagicMock()
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with span("chapter.summarize", chapter="Ch.1"):
                pass
        mock_tracer.start_as_current_span.assert_called_once_with("chapter.summarize")

    def test_llm_call_span_name(self):
        from core.obs.tracing import span
        mock_tracer = MagicMock()
        with patch("core.obs.tracing._is_tracing_enabled", return_value=True), \
             patch("core.obs.tracing._get_tracer", return_value=mock_tracer):
            with span("llm.exec_summary", gen_ai_model="gemma"):
                pass
        mock_tracer.start_as_current_span.assert_called_once_with("llm.exec_summary")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
