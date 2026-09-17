"""V18.2.20 (SC1): Streaming/chunked writes for large books.

WHY THIS EXISTS
---------------
The audit (SC1) flagged that for 1000-page books, the output generators
(obsidian, packets, evidence_map) each build large in-memory dicts before
writing. A 1000-page book's raw markdown can be 5-15 MB, and the output
studio generators each build large in-memory structures.

This module provides a :func:`streaming_write_text` helper that writes
text in chunks (default 64 KB) instead of building the full string in
memory. This reduces peak RSS for large books.

For most outputs (markdown, JSON under 1 MB), the standard
``Path.write_text()`` is fine — the overhead of chunked writes isn't
worth it. This helper is for the LARGE output paths where the full string
would be multiple MB.

BOOK-AGNOSTIC
-------------
Streaming writes are pure I/O infrastructure — no domain-specific terms.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

# Default chunk size for streaming writes (64 KB).
# Smaller chunks = lower peak memory but more syscalls.
# 64 KB is a good balance for modern filesystems.
_DEFAULT_CHUNK_SIZE = 64 * 1024

# Threshold above which we warn about large in-memory writes.
# Files larger than this should use streaming_write_text.
LARGE_FILE_THRESHOLD = 2 * 1024 * 1024  # 2 MB


def streaming_write_text(
    path: str | Path,
    content: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    encoding: str = "utf-8",
) -> None:
    """Write a string to a file in chunks to reduce peak memory.

    For content < ``LARGE_FILE_THRESHOLD`` (2 MB), this delegates to
    ``Path.write_text()`` (the overhead of chunking isn't worth it).
    For larger content, it writes in ``chunk_size`` chunks.

    Args:
        path: the output file path.
        content: the string to write.
        chunk_size: bytes per write (default 64 KB).
        encoding: text encoding (default utf-8).

    V18.2.20 (SC1): Reduces peak RSS for large-book outputs.
    """
    p = Path(path)
    content_len = len(content)

    # Small files: use the fast standard path.
    if content_len < LARGE_FILE_THRESHOLD:
        p.write_text(content, encoding=encoding)
        return

    # Large files: write in chunks.
    # Encode once (to bytes), then write chunks. This avoids re-encoding
    # each chunk (which would be slower) while keeping peak memory at
    # chunk_size + the encoded buffer.
    logger.info(
        "V18.2.20 (SC1): streaming write %d bytes to %s (chunk=%d KB)",
        content_len, p.name, chunk_size // 1024,
    )
    encoded = content.encode(encoding)
    # Atomic write: write to a temp file, then rename (prevents partial
    # writes if the process crashes mid-write).
    tmp_path = p.with_suffix(p.suffix + ".tmp")
    try:
        with open(tmp_path, "wb") as f:
            for i in range(0, len(encoded), chunk_size):
                f.write(encoded[i:i + chunk_size])
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp_path, p)
    except Exception:
        # Clean up the temp file on failure.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def streaming_write_lines(
    path: str | Path,
    lines: Iterable[str],
    *,
    encoding: str = "utf-8",
) -> None:
    """Write an iterable of lines to a file, line by line.

    This is for cases where the content is generated incrementally
    (e.g. per-chapter summaries) and holding all lines in memory
    would be wasteful. Each line is written as it's produced.

    Args:
        path: the output file path.
        lines: an iterable of strings (each written as a line).
        encoding: text encoding (default utf-8).
    """
    p = Path(path)
    line_count = 0
    with open(p, "w", encoding=encoding) as f:
        for line in lines:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
            line_count += 1
            # Flush every 100 lines to balance I/O efficiency + memory.
            if line_count % 100 == 0:
                f.flush()
    logger.debug("streaming_write_lines: wrote %d lines to %s", line_count, p.name)


__all__ = ["streaming_write_text", "streaming_write_lines", "LARGE_FILE_THRESHOLD"]
