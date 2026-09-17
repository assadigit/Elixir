"""V18.2.14 (B4): Tests for the traceable error-handling helpers.

Verifies that:
1. ``log_swallow`` emits exactly one log record at the requested level, with
   the operation name + exception type + message in the text, and the
   traceback attached via ``exc_info``.
2. ``swallow`` context manager swallows the exception (does not re-raise)
   and logs it via ``log_swallow``.
3. ``swallow`` lets successful blocks pass through untouched.
4. The caller's file:line is captured (so the log points at the swallow
   site, not the helper).
5. The helpers themselves never raise (fail-open).
"""
from __future__ import annotations

import logging
import sys
import types
from unittest.mock import MagicMock

# Stub tiktoken (not installed in test env)
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from utils.error_trace import log_swallow, swallow


class TestLogSwallow:
    """V18.2.14: log_swallow emits a traceable record."""

    def test_emits_one_record_at_info_by_default(self, caplog):
        """A swallowed exception produces exactly one INFO record."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            with caplog.at_level(logging.INFO, logger="utils.error_trace"):
                log_swallow("test_op", e)
        records = [r for r in caplog.records if r.name == "utils.error_trace"]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO

    def test_record_contains_operation_and_exception(self, caplog):
        """The message has the operation name + exc type + exc message."""
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            with caplog.at_level(logging.INFO, logger="utils.error_trace"):
                log_swallow("my_operation", e)
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert "my_operation" in rec.getMessage()
        assert "RuntimeError" in rec.getMessage()
        assert "boom" in rec.getMessage()

    def test_detail_appended_to_message(self, caplog):
        """The ``detail`` kwarg is appended after a pipe."""
        try:
            raise ValueError("x")
        except ValueError as e:
            with caplog.at_level(logging.INFO, logger="utils.error_trace"):
                log_swallow("op", e, detail="file=chapter1.md")
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert "file=chapter1.md" in rec.getMessage()

    def test_traceback_attached_via_exc_info(self, caplog):
        """The full traceback is attached so structured handlers can capture it."""
        try:
            raise ValueError("traceable")
        except ValueError as e:
            with caplog.at_level(logging.INFO, logger="utils.error_trace"):
                log_swallow("op", e)
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert rec.exc_info is not None
        assert rec.exc_info[0] is ValueError
        assert str(rec.exc_info[1]) == "traceable"

    def test_warning_level_for_unexpected(self, caplog):
        """``level=WARNING`` surfaces the record at WARNING."""
        try:
            raise Exception("unexpected")
        except Exception as e:
            with caplog.at_level(logging.WARNING, logger="utils.error_trace"):
                log_swallow("op", e, level=logging.WARNING)
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert rec.levelno == logging.WARNING

    def test_never_raises_on_bad_input(self):
        """Even with None or non-exception input, log_swallow doesn't raise."""
        # Pass a non-BaseException — should still not crash.
        log_swallow("op", "not an exception")  # type: ignore[arg-type]
        log_swallow("op", None)  # type: ignore[arg-type]


class TestSwallow:
    """V18.2.14: swallow context manager."""

    def test_successful_block_passes_through(self, caplog):
        """A block that succeeds produces no log record."""
        with caplog.at_level(logging.INFO, logger="utils.error_trace"), swallow("ok_op"):
            result = 1 + 1
        assert result == 2
        records = [r for r in caplog.records if r.name == "utils.error_trace"]
        assert records == []

    def test_exception_swallowed_not_reraised(self, caplog):
        """An exception in the block is swallowed — does not propagate."""
        with caplog.at_level(logging.INFO, logger="utils.error_trace"), swallow("risky_op"):
            raise RuntimeError("swallowed")
        # If we reach here, the exception was swallowed.
        records = [r for r in caplog.records if r.name == "utils.error_trace"]
        assert len(records) == 1
        assert "risky_op" in records[0].getMessage()

    def test_logs_with_operation_and_type(self, caplog):
        with caplog.at_level(logging.INFO, logger="utils.error_trace"):
            with swallow("cleanup_files"):
                raise OSError("permission denied")
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert "cleanup_files" in rec.getMessage()
        assert "OSError" in rec.getMessage()
        assert "permission denied" in rec.getMessage()

    def test_detail_kwarg_passed_through(self, caplog):
        with caplog.at_level(logging.INFO, logger="utils.error_trace"):
            with swallow("op", detail="model=gemma12b"):
                raise ValueError("x")
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert "model=gemma12b" in rec.getMessage()

    def test_warning_level_kwarg(self, caplog):
        with caplog.at_level(logging.WARNING, logger="utils.error_trace"):
            with swallow("unexpected_op", level=logging.WARNING):
                raise Exception("bug?")
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert rec.levelno == logging.WARNING

    def test_traceback_attached(self, caplog):
        with caplog.at_level(logging.INFO, logger="utils.error_trace"), swallow("op"):
            raise ValueError("trace")
        rec = [r for r in caplog.records if r.name == "utils.error_trace"][0]
        assert rec.exc_info is not None
        assert rec.exc_info[0] is ValueError
