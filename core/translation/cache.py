"""V7.2.0 S5: Persistent translation cache.

Caches translation results keyed by (text_hash, source_lang, target_lang,
model_hash). If a chunk was already translated and validated, skip it
entirely — saves hours on re-runs and crash recovery.

Cache location: ``~/.elixir/translation_cache/``
Cache format: JSON files named ``{hash}.json`` containing::

    {
        "text_hash": "abc123...",
        "source_lang": "en",
        "target_lang": "fa",
        "model": "facebook/nllb-200-distilled-600M",
        "translated_text": "هوش مصنوعی...",
        "similarity_score": 0.82,
        "judge_score": 0.85,
        "passed": true,
        "created_at": "2026-07-19T14:30:00",
        "text_preview": "Artificial intelligence is..."
    }

V10.33.0 (Sprint 5.4): Added FIFO eviction cap (default 2000 entries).
Before V10.33.0 the cache was unbounded — a 20-chapter book with heavy
translation could leave thousands of files that were never cleaned up.
The cap evicts the oldest entries (by ``created_at`` timestamp) when the
file count exceeds the limit.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".elixir" / "translation_cache"

#: V10.33.0 (Sprint 5.4): Maximum number of cache entries (FIFO eviction).
#: The V10.27.0 audit found the cache was unbounded — this cap prevents
#: unbounded disk growth.  2000 entries ≈ 200 MB (each entry ~100 KB).
MAX_CACHE_ENTRIES = 2000


def _ensure_cache_dir() -> Path:
    """Ensure the cache directory exists."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _cache_key(
    text: str,
    source_lang: str,
    target_lang: str,
    model: str,
    glossary_hash: str = "",
) -> str:
    """Build a cache key hash from all parameters that affect the translation."""
    key_str = f"{source_lang}->{target_lang}:{model}:{glossary_hash}:{text}"
    return hashlib.md5(key_str.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    """Get the file path for a cache key."""
    return _ensure_cache_dir() / f"{key}.json"


def get_cached_translation(
    text: str,
    source_lang: str,
    target_lang: str,
    model: str,
    glossary_hash: str = "",
) -> dict | None:
    """Look up a cached translation.

    Returns the cached entry dict, or None if not found.
    """
    key = _cache_key(text, source_lang, target_lang, model, glossary_hash)
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Verify the text matches (defense against hash collisions)
        if data.get("text_preview", "")[:100] != text[:100]:
            return None
        return data
    except OSError:
        return None


def save_cached_translation(
    text: str,
    source_lang: str,
    target_lang: str,
    model: str,
    translated_text: str,
    similarity_score: float = 0.0,
    judge_score: float = 0.0,
    passed: bool = True,
    glossary_hash: str = "",
) -> None:
    """Save a translation result to the cache."""
    key = _cache_key(text, source_lang, target_lang, model, glossary_hash)
    path = _cache_path(key)
    try:
        data = {
            "text_hash": key,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model": model,
            "translated_text": translated_text,
            "similarity_score": similarity_score,
            "judge_score": judge_score,
            "passed": passed,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "text_preview": text[:200],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        # V10.33.0 (Sprint 5.4): enforce the FIFO cap after each save.
        _evict_if_needed()
    except OSError:
        pass  # Cache saving should never crash


def _evict_if_needed(max_entries: int = MAX_CACHE_ENTRIES) -> int:
    """V10.33.0 (Sprint 5.4): Evict oldest cache entries if over the cap.

    Uses the ``created_at`` field in each JSON file to determine age.
    Files without ``created_at`` are evicted first (treated as oldest).

    Returns the number of files evicted.
    """
    if not _CACHE_DIR.exists():
        return 0
    files = list(_CACHE_DIR.glob("*.json"))
    if len(files) <= max_entries:
        return 0
    # Sort by created_at (oldest first).  Read each file to get the timestamp.
    # This is O(n) reads but only runs when the cap is exceeded — not on every save.
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            created = data.get("created_at", "")
        except Exception as _e:
            created = ""
        entries.append((created, f))
    # Sort by created_at ascending (oldest first); empty strings sort first
    entries.sort(key=lambda x: x[0])
    # Evict the oldest (len - max_entries) files
    to_evict = len(files) - max_entries
    evicted = 0
    for _ts, f in entries[:to_evict]:
        try:
            f.unlink()
            evicted += 1
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
    if evicted > 0:
        logger.debug("Translation cache FIFO: evicted %d entries (cap=%d)", evicted, max_entries)
    return evicted
