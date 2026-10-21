"""Token counting and truncation using tiktoken with fallback to approximate count."""

import hashlib
import logging
import os
import sys
from collections import OrderedDict

import tiktoken

logger = logging.getLogger(__name__)
_ENCODER: tiktoken.Encoding | None = None

# V13.27.0 (P2.7): Bounded token counter cache (was unbounded dict).
# Keyed by sha256(text). During a 20-chapter book conversion, this cache
# can accumulate thousands of entries (one per unique text passed to
# count_tokens). Capped at 500 entries with FIFO eviction.
_TOKEN_COUNTER_CACHE: "OrderedDict[str, int]" = OrderedDict()
_TOKEN_CACHE_MAX = 500


def seed_offline_encoding_cache() -> None:
    """V0.6.63: seed tiktoken's encoding cache from the bundled copy.

    Frozen installs only (no-op from source): copies the vendored
    cl100k_base blob from ``assets/tiktoken/`` into
    ``<user_data>/tiktoken_cache`` and points ``DATA_GYM_CACHE_DIR`` there,
    so token counting is exact with no network on first use. Best-effort —
    never raises (the word-count approximation remains the fallback).
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        import shutil

        from app_paths import resource_path
        from utils.settings import user_data_dir

        cache_dir = user_data_dir() / "tiktoken_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        for blob in resource_path("assets", "tiktoken").glob("*.tiktoken"):
            dest = cache_dir / blob.name
            if not dest.exists():
                shutil.copy2(blob, dest)
        os.environ.setdefault("DATA_GYM_CACHE_DIR", str(cache_dir))
    except Exception:  # noqa: BLE001 — best-effort by contract
        logger.debug("offline encoding cache seed skipped", exc_info=True)


def _get_encoder() -> tiktoken.Encoding | None:
    global _ENCODER
    if _ENCODER is None:
        try:
            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = None
    return _ENCODER


def count_tokens(text: str, use_cache: bool = True) -> int:
    """Count tokens using cl100k_base. Falls back to word-based approximation."""
    if not text:
        return 0
    cache_key = None
    if use_cache:
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if cache_key in _TOKEN_COUNTER_CACHE:
            # V13.27.0: Move to end (LRU-style — most recently used stays)
            _TOKEN_COUNTER_CACHE.move_to_end(cache_key)
            return _TOKEN_COUNTER_CACHE[cache_key]

    encoder = _get_encoder()
    if encoder:
        try:
            tokens = len(encoder.encode(text))
        except Exception:
            tokens = len(text.split()) * 4 // 3
    else:
        tokens = len(text.split()) * 4 // 3

    if use_cache and cache_key:
        _TOKEN_COUNTER_CACHE[cache_key] = tokens
        # V13.27.0 (P2.7): Evict oldest if over the cap
        while len(_TOKEN_COUNTER_CACHE) > _TOKEN_CACHE_MAX:
            _TOKEN_COUNTER_CACHE.popitem(last=False)  # FIFO eviction
    return tokens


def truncate_by_tokens(text: str, max_tokens: int, add_ellipsis: bool = True) -> str:
    """Truncate text to at most max_tokens."""
    if max_tokens <= 0:
        return ""
    if count_tokens(text) <= max_tokens:
        return text

    encoder = _get_encoder()
    if encoder:
        try:
            tokens = encoder.encode(text)
            truncated_tokens = tokens[:max_tokens]
            truncated = encoder.decode(truncated_tokens)
            if add_ellipsis and count_tokens(truncated + "…") <= max_tokens:
                truncated += "…"
            return truncated
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    max_chars = max_tokens * 4
    truncated = text[:max_chars]
    if add_ellipsis and len(truncated) < len(text):
        truncated += "…"
    return truncated
