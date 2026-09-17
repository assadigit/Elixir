"""V18.10 (Phase 6.3): GGUF checksum verification.

On first model load, compute SHA-256 of the first 1MB + last 1MB of the
GGUF file. Store in a cache file. On subsequent loads, verify the checksum
matches — detects file corruption or accidental replacement.

This is additive — if the checksum fails, a WARNING is logged but the
load proceeds (fail-open, not fail-closed). The user can investigate.

Usage::

    from core.llm.gguf_checksum import verify_gguf_checksum
    is_ok, reason = verify_gguf_checksum("/path/to/model.gguf")
    if not is_ok:
        logger.warning("GGUF checksum mismatch: %s", reason)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["compute_gguf_checksum", "verify_gguf_checksum", "get_checksum_cache_path"]

# Compute SHA-256 of the first 1MB + last 1MB only (not the whole file).
# A 7.79 GB GGUF would take ~30s to fully hash; the first+last 1MB captures
# both the header (GGUF magic, tensor info) and the tail (final weights).
_CHUNK_SIZE = 1024 * 1024  # 1 MB


def get_checksum_cache_path() -> Path:
    """Return the path to the checksum cache file.

    Stored in ``~/.markitdown_pro/gguf_checksums.json``.
    """
    cache_dir = Path.home() / ".markitdown_pro"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / "gguf_checksums.json"


def compute_gguf_checksum(gguf_path: str | Path) -> str:
    """Compute the SHA-256 checksum of the first + last 1MB of a GGUF file.

    Returns a hex string. For files < 2MB, the whole file is hashed.
    """
    gguf_path = Path(gguf_path)
    if not gguf_path.exists():
        raise FileNotFoundError(f"GGUF file not found: {gguf_path}")

    file_size = gguf_path.stat().st_size
    hasher = hashlib.sha256()

    with open(gguf_path, "rb") as f:
        # Hash the first 1MB
        first_chunk = f.read(_CHUNK_SIZE)
        hasher.update(first_chunk)

        # If the file is > 2MB, hash the last 1MB too
        if file_size > 2 * _CHUNK_SIZE:
            f.seek(file_size - _CHUNK_SIZE)
            last_chunk = f.read(_CHUNK_SIZE)
            hasher.update(last_chunk)
        elif file_size > _CHUNK_SIZE:
            # File is between 1MB and 2MB — hash the middle portion too
            middle = f.read()
            hasher.update(middle)

    return hasher.hexdigest()


def _load_cache() -> dict:
    """Load the checksum cache. Returns empty dict if missing/corrupt."""
    cache_path = get_checksum_cache_path()
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    """Save the checksum cache."""
    cache_path = get_checksum_cache_path()
    cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def verify_gguf_checksum(gguf_path: str | Path) -> tuple[bool, str]:
    """Verify a GGUF file's checksum against the cache.

    Returns ``(is_ok, reason)``:
    - ``(True, "checksum matched")`` — file matches the cached checksum.
    - ``(True, "checksum registered")`` — first load, checksum stored.
    - ``(False, "checksum mismatch: expected X, got Y")`` — file changed.
    - ``(False, "file not found")`` — GGUF doesn't exist.

    This is fail-open: a mismatch logs a WARNING but doesn't block the load.
    The caller decides whether to proceed (recommended: proceed + warn).
    """
    gguf_path = Path(gguf_path)
    if not gguf_path.exists():
        return False, "file not found"

    try:
        current_checksum = compute_gguf_checksum(gguf_path)
    except Exception as e:
        return False, f"checksum computation failed: {e}"

    cache = _load_cache()
    cache_key = str(gguf_path.resolve())

    if cache_key not in cache:
        # First load — register the checksum
        cache[cache_key] = {
            "checksum": current_checksum,
            "file_size": gguf_path.stat().st_size,
            "path": cache_key,
        }
        _save_cache(cache)
        return True, "checksum registered"

    cached_checksum = cache[cache_key].get("checksum", "")
    if current_checksum == cached_checksum:
        return True, "checksum matched"

    return False, f"checksum mismatch: expected {cached_checksum[:16]}…, got {current_checksum[:16]}…"
