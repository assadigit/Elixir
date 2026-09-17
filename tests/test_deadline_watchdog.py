"""V18.2.22 (BUG-4) — Tests for the mid-generation deadline watchdog.

Covers:
1. _deadline_exceeded returns False when no deadline is set (0)
2. _deadline_exceeded returns False when deadline not yet exceeded
3. _deadline_exceeded returns True and logs WARNING when exceeded
4. _deadline_exceeded returns False when _chapter_deadline_start is None
5. _deadline_exceeded returns False for cloud (non-local) providers
6. The optional phases (scholar reflection, dedup, consolidation) are
   skipped when the deadline is exceeded
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestDeadlineExceeded:
    """Test the _deadline_exceeded helper directly."""

    def _make_summarizer_stub(self, deadline=0, start=None, is_local=True):
        """Create a minimal stub with just the fields _deadline_exceeded needs."""
        stub = MagicMock()
        stub.local_chapter_deadline = deadline
        stub._chapter_deadline_start = start
        stub.is_local = is_local
        stub._deadline_exceeded = lambda phase: _deadline_exceeded_impl(
            stub, phase
        )
        return stub

    def test_no_deadline_returns_false(self):
        """When local_chapter_deadline is 0, never skip."""
        stub = self._make_summarizer_stub(deadline=0, start=time.time())
        assert stub._deadline_exceeded("test") is False

    def test_no_start_time_returns_false(self):
        """When _chapter_deadline_start is None, never skip."""
        stub = self._make_summarizer_stub(deadline=480, start=None)
        assert stub._deadline_exceeded("test") is False

    def test_cloud_provider_returns_false(self):
        """Cloud providers don't have VRAM stalls — never skip."""
        stub = self._make_summarizer_stub(deadline=480, start=time.time(), is_local=False)
        assert stub._deadline_exceeded("test") is False

    def test_not_yet_exceeded_returns_false(self):
        """When elapsed < deadline, don't skip."""
        stub = self._make_summarizer_stub(deadline=480, start=time.time())
        assert stub._deadline_exceeded("test") is False

    def test_exceeded_returns_true_and_logs(self):
        """When elapsed > deadline, return True and log WARNING."""
        # Start time 500 seconds ago, deadline 480
        stub = self._make_summarizer_stub(
            deadline=480, start=time.time() - 500
        )
        logs = []
        stub.log = lambda msg, level: logs.append((msg, level))
        stub._deadline_exceeded = lambda phase: _deadline_exceeded_impl(stub, phase)
        result = stub._deadline_exceeded("scholar reflection")
        assert result is True
        assert len(logs) == 1
        msg, level = logs[0]
        assert level == "WARNING"
        assert "Deadline exceeded" in msg
        assert "scholar reflection" in msg
        assert "500" in msg or "480" in msg  # elapsed or deadline

    def test_just_under_deadline_returns_false(self):
        """When elapsed is 1s under deadline, don't skip."""
        stub = self._make_summarizer_stub(
            deadline=480, start=time.time() - 479
        )
        assert stub._deadline_exceeded("test") is False


def _deadline_exceeded_impl(summarizer, phase_name: str) -> bool:
    """The actual implementation, mirrored from summarizer.py for testing.

    This avoids importing the full Summarizer (which pulls in tiktoken etc.).
    """
    if not summarizer.is_local or summarizer.local_chapter_deadline <= 0:
        return False
    if summarizer._chapter_deadline_start is None:
        return False
    elapsed = time.time() - summarizer._chapter_deadline_start
    if elapsed > summarizer.local_chapter_deadline:
        summarizer.log(
            f"  ⏱️⚠️ Deadline exceeded ({elapsed:.0f}s > "
            f"{summarizer.local_chapter_deadline}s) — skipping optional phase: "
            f"{phase_name}",
            "WARNING",
        )
        return True
    return False


class TestDeadlineWatchdogIntegration:
    """Test that the deadline watchdog is wired into _summarize_inner by
    verifying the code structure (static analysis of the source file)."""

    def test_deadline_check_before_scholar_reflection(self):
        """The scholar reflection phase must be guarded by _deadline_exceeded."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        # Find the scholar reflection block
        scholar_idx = content.find("_deadline_exceeded(\"scholar reflection\")")
        assert scholar_idx > 0, "scholar reflection must be guarded by _deadline_exceeded"
        # Verify it's BEFORE the _scholar_reflection call
        scholar_call_idx = content.find(
            "self._scholar_reflection_gapfill_only(heading, content, parsed)",
            scholar_idx,
        )
        assert scholar_call_idx > scholar_idx, \
            "_deadline_exceeded must come before _scholar_reflection"

    def test_deadline_check_before_semantic_dedup(self):
        """The semantic dedup phase must be guarded by _deadline_exceeded."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        dedup_idx = content.find("_deadline_exceeded(\"semantic dedup\")")
        assert dedup_idx > 0, "semantic dedup must be guarded by _deadline_exceeded"
        dedup_call_idx = content.find("self._semantic_dedup_bullets(bullets)", dedup_idx)
        assert dedup_call_idx > dedup_idx, \
            "_deadline_exceeded must come before _semantic_dedup_bullets"

    def test_deadline_check_before_consolidation(self):
        """The consolidation phase must be guarded by _deadline_exceeded."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        consol_idx = content.find("_deadline_exceeded(\"bullet consolidation\")")
        assert consol_idx > 0, "consolidation must be guarded by _deadline_exceeded"
        # V18.20.3.7: the call site gained a heading kwarg (RC-A coverage
        # assertion) — match on the prefix, the ordering intent is unchanged.
        consol_call_idx = content.find("self._consolidate_bullets(bullets", consol_idx)
        assert consol_call_idx > consol_idx, \
            "_deadline_exceeded must come before _consolidate_bullets"

    def test_deadline_start_set_in_summarize_chapters(self):
        """summarize_chapters must set _chapter_deadline_start before _summarize_inner."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        start_idx = content.find("self._chapter_deadline_start = _chap_start")
        assert start_idx > 0, "_chapter_deadline_start must be set in summarize_chapters"
        inner_idx = content.find("_result = self._summarize_inner(", start_idx)
        assert inner_idx > start_idx, \
            "_chapter_deadline_start must be set BEFORE _summarize_inner is called"

    def test_helper_method_exists(self):
        """The _deadline_exceeded method must be defined on the Summarizer."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        assert "def _deadline_exceeded(self, phase_name: str) -> bool:" in content, \
            "_deadline_exceeded method must be defined"


class TestEmptyOCRModelWarning:
    """BUG-5: warn when LLM OCR is enabled but primary_ocr_model is empty."""

    def test_warning_in_settings_logger(self):
        """settings_logger.py must warn when use_llm_ocr=True and model empty."""
        logger_path = _project_root / "core" / "pipeline" / "conversion" / "settings_logger.py"
        content = logger_path.read_text(encoding="utf-8")
        assert "primary_ocr_model is EMPTY" in content or \
               "primary_ocr_model is empty" in content, \
            "settings_logger must warn about empty primary_ocr_model"
        assert "WARNING" in content

    def test_warning_only_when_ocr_enabled(self):
        """The warning must be gated on r.use_llm_ocr (not unconditional)."""
        logger_path = _project_root / "core" / "pipeline" / "conversion" / "settings_logger.py"
        content = logger_path.read_text(encoding="utf-8")
        assert "r.use_llm_ocr and not r.primary_ocr_model" in content, \
            "warning must be gated on use_llm_ocr AND empty model"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
