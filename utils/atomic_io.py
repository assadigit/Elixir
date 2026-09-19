"""V9.0.0: Atomic file write utilities.

Provides ``atomic_write_text`` and ``atomic_write_json`` that write to a
temporary file in the same directory, fsync, then ``os.replace()`` to the
final path.  This ensures that a crash mid-write never leaves a partial
file — the reader either sees the complete old file or the complete new
file, never a truncated mix.

Used by:
- Summary file writes (converter.py) — prevents partial summaries being
  mistaken for complete ones by the chapter-resume system.
- Settings persistence (utils/settings.py) — prevents settings.json
  corruption from concurrent writes.
- Checkpoint saves (core/pipeline/checkpoint.py) — prevents corrupted
  checkpoint state after a crash.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Write ``content`` to ``path`` atomically.

    Writes to a temp file in the same directory, flushes, fsyncs, then
    renames to the final path via ``os.replace()`` (atomic on all
    platforms).  If the process crashes during the write, the temp file
    is left behind (harmless) and the original file is untouched.

    Raises OSError (including disk-full) to the caller — never swallows
    disk-full errors.  The caller is responsible for logging and recovery.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.stem}_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except OSError:
        # Clean up the temp file on failure (including disk-full)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        # Re-raise — caller must handle (e.g. log + skip, not swallow)
        raise
    except Exception:
        # Clean up on any other failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(
    path: str | Path, data: Any, indent: int = 2, ensure_ascii: bool = False
) -> None:
    """Write ``data`` as JSON to ``path`` atomically."""
    content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    atomic_write_text(path, content)
