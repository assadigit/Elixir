"""Tests for Phase 6: atomic I/O, filename sanitization, Ollama supervisor."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── atomic_write_text disk-full handling ──────────────────────────────────


def test_atomic_write_text_success(tmp_path: Path) -> None:
    """Normal write should succeed."""
    from utils.atomic_io import atomic_write_text

    p = tmp_path / "test.txt"
    atomic_write_text(p, "hello world")
    assert p.read_text() == "hello world"


def test_atomic_write_text_raises_on_disk_full(tmp_path: Path) -> None:
    """Disk-full (OSError) should be raised, not swallowed."""
    from utils.atomic_io import atomic_write_text

    # Simulate disk-full by writing to a read-only directory
    ro_dir = tmp_path / "readonly"
    ro_dir.mkdir()
    os.chmod(str(ro_dir), 0o444)
    try:
        p = ro_dir / "test.txt"
        try:
            atomic_write_text(p, "hello")
            raise AssertionError("Should have raised OSError")
        except OSError:
            pass  # correct — error is surfaced
    finally:
        os.chmod(str(ro_dir), 0o755)


def test_atomic_write_json_success(tmp_path: Path) -> None:
    """JSON write should succeed."""
    from utils.atomic_io import atomic_write_json

    p = tmp_path / "test.json"
    atomic_write_json(p, {"key": "value"})
    import json

    assert json.loads(p.read_text())["key"] == "value"


# ── Filename sanitization ─────────────────────────────────────────────────


def test_sanitize_filename_basic() -> None:
    """Basic filename should pass through."""
    from utils.filename import sanitize_filename

    assert sanitize_filename("test.txt") == "test.txt"


def test_sanitize_filename_strips_zwj() -> None:
    """Zero-width joiner should be stripped."""
    from utils.filename import sanitize_filename

    assert sanitize_filename("test\u200dfamily.txt") == "testfamily.txt"


def test_sanitize_filename_strips_rtl_mark() -> None:
    """RTL mark should be stripped."""
    from utils.filename import sanitize_filename

    assert sanitize_filename("test\u200f.txt") == "test.txt"


def test_sanitize_filename_strips_bom() -> None:
    """BOM should be stripped."""
    from utils.filename import sanitize_filename

    assert sanitize_filename("\ufefftest.txt") == "test.txt"


def test_sanitize_filename_windows_illegal() -> None:
    """Windows-illegal characters should be replaced."""
    from utils.filename import sanitize_filename

    result = sanitize_filename('file<>:"/\\|?*.txt')
    assert "<" not in result
    assert ">" not in result
    assert ":" not in result
    assert '"' not in result


def test_sanitize_filename_empty() -> None:
    """Empty string should return 'unnamed'."""
    from utils.filename import sanitize_filename

    assert sanitize_filename("") == "unnamed"


def test_sanitize_filename_length_limit() -> None:
    """Filename should be truncated to 200 chars."""
    from utils.filename import sanitize_filename

    long_name = "a" * 300 + ".txt"
    result = sanitize_filename(long_name)
    assert len(result) <= 200


def test_sanitize_heading_for_filename() -> None:
    """Heading sanitization should remove quotes and colons."""
    from utils.filename import sanitize_heading_for_filename

    result = sanitize_heading_for_filename('Chapter 2: "The Beginning"')
    assert ":" not in result
    assert '"' not in result
    assert len(result) > 0


# ── Ollama supervisor ─────────────────────────────────────────────────────


def test_ollama_supervisor_init() -> None:
    """Supervisor should initialize with defaults."""
    from core.system.ollama_supervisor import OllamaSupervisor

    sup = OllamaSupervisor()
    assert sup._max_failures == 3
    assert sup._consecutive_failures == 0


def test_ollama_supervisor_record_success_resets() -> None:
    """record_success should reset the failure counter."""
    from core.system.ollama_supervisor import OllamaSupervisor

    sup = OllamaSupervisor()
    sup._consecutive_failures = 2
    sup.record_success()
    assert sup._consecutive_failures == 0


def test_ollama_supervisor_record_failure_increments() -> None:
    """record_failure should increment the counter."""
    from core.system.ollama_supervisor import OllamaSupervisor

    sup = OllamaSupervisor(max_consecutive_failures=10)
    sup.record_failure()
    assert sup._consecutive_failures == 1


def test_ollama_supervisor_no_restart_when_below_threshold() -> None:
    """Should not attempt restart when below threshold."""
    from core.system.ollama_supervisor import OllamaSupervisor

    sup = OllamaSupervisor(max_consecutive_failures=5)
    result = sup.record_failure()  # failure #1, threshold is 5
    assert result is False  # no restart attempted


# ── 0-page PDF guard ──────────────────────────────────────────────────────


def test_zero_page_guard_pattern() -> None:
    """The 0-page guard pattern should be present in the extraction phase.

    V10.8.0 (Phase 8C): the guard moved from converter.py to
    conversion/extraction.py when the extraction phase was extracted.
    Both files are checked — the analyzer's EmptyPdfError is the primary
    guard (analyzer.py), the extraction module's guard is belt-and-suspenders.
    """
    # Primary guard: analyzer raises EmptyPdfError (V10.4.0 Phase 6A-1)
    with open(_project_root / "core" / "pdf" / "analyzer.py") as f:
        analyzer_content = f.read()
    assert "EmptyPdfError" in analyzer_content
    assert "total_pages == 0" in analyzer_content

    # Belt-and-suspenders guard: extraction module (V10.8.0 — was converter.py)
    with open(_project_root / "core" / "pipeline" / "conversion" / "extraction.py") as f:
        extraction_content = f.read()
    assert "total_pages == 0" in extraction_content
    assert "PDF has 0 pages" in extraction_content
