"""V18.1 (audit O1/P2): On-disk embedding cache.

Previously, ``SentenceTransformer.encode()`` was called on every
``semantic_fact_check`` / ``content_judge`` / ``keypoints_builder`` call —
re-encoding the same source sentences for every chapter. For a 20-chapter
book with 50 sentences/chapter, that's ~1000 redundant encodings per run.

This module provides a persistent disk cache keyed by
``sha1(model_name + text)`` → embedding vector (numpy array, stored as
.npy). Lookups are O(1) disk reads; misses fall through to the model and
store the result.

Thread-safe (file-lock per cache entry). Backed by ``~/.elixir/
embed_cache/<model_dir>/`` so switching models doesn't invalidate the old
cache (entries are namespaced by model).

Usage::

    from core.llm.embed_cache import embed_cache
    vec = embed_cache.get_or_encode(model, text, model_name="BAAI/bge-base-en-v1.5")
    # or batch:
    vecs = embed_cache.get_or_encode_batch(model, texts, model_name=...)
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cache root — ~/.elixir/embed_cache/
_CACHE_ROOT: Path = Path.home() / ".elixir" / "embed_cache"

# Per-entry file lock (prevents two threads writing the same .npy simultaneously)
_locks: dict = {}
_locks_guard = threading.Lock()


def _entry_lock(key: str) -> threading.Lock:
    """Return a per-key lock (created lazily)."""
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.Lock()
        return _locks[key]


def _model_dir_name(model_name: str) -> str:
    """Convert a model name to a safe directory name.

    ``BAAI/bge-base-en-v1.5`` → ``BAAI--bge-base-en-v1.5``
    ``all-MiniLM-L6-v2``      → ``all-MiniLM-L6-v2``
    """
    return model_name.replace("/", "--").replace("\\", "--")


def _text_hash(text: str) -> str:
    """SHA1 of the text (truncated to 16 chars for filename brevity)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


class EmbedCache:
    """Persistent on-disk embedding cache.

    Stores one ``.npy`` file per (model, text) pair. The filename is
    ``<model_dir>/<sha1_prefix>.npy``. Each file contains a single numpy
    array (the embedding vector).

    The cache is **append-only** — entries are never evicted automatically.
    For a typical 20-chapter book with ~1000 unique sentences, the cache
    grows by ~3 MB (1000 × 768-dim × 4 bytes). Users can clear it manually
    by deleting the ``~/.elixir/embed_cache/`` directory.
    """

    def __init__(self, cache_root: Path | None = None) -> None:
        self._root = cache_root or _CACHE_ROOT
        self._enabled = True

    @property
    def root(self) -> Path:
        return self._root

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable caching (when off, all ops are no-ops)."""
        self._enabled = enabled

    def _path_for(self, model_name: str, text: str) -> Path:
        return self._root / _model_dir_name(model_name) / f"{_text_hash(text)}.npy"

    def get(self, text: str, model_name: str) -> Any | None:
        """Return cached embedding for ``text`` + ``model_name``, or None."""
        if not self._enabled:
            return None
        try:
            path = self._path_for(model_name, text)
            if not path.exists():
                return None
            import numpy as np
            return np.load(str(path), allow_pickle=False)
        except Exception as exc:
            logger.debug("embed cache get failed: %s: %s", type(exc).__name__, exc)
            return None

    def put(self, text: str, model_name: str, vector: Any) -> None:
        """Store an embedding in the cache (best-effort)."""
        if not self._enabled:
            return
        try:
            import numpy as np
            path = self._path_for(model_name, text)
            with _entry_lock(path.stem):
                path.parent.mkdir(parents=True, exist_ok=True)
                # Write to a temp file then rename (atomic on same filesystem)
                tmp = path.with_suffix(".npy.tmp")
                np.save(str(tmp), np.asarray(vector), allow_pickle=False)
                tmp.replace(path)
        except Exception as exc:
            logger.debug("embed cache put failed: %s: %s", type(exc).__name__, exc)

    def get_or_encode(
        self,
        model: Any,
        text: str,
        model_name: str = "",
    ) -> Any:
        """Return cached embedding, or encode + cache."""
        # Try cache first
        cached = self.get(text, model_name)
        if cached is not None:
            return cached
        # Encode
        vec = model.encode(text, convert_to_numpy=True)
        self.put(text, model_name, vec)
        return vec

    def get_or_encode_batch(
        self,
        model: Any,
        texts: Sequence[str],
        model_name: str = "",
    ) -> list[Any]:
        """Batch encode with cache hits. Only uncached texts are encoded."""
        if not self._enabled:
            # Fast path — no cache, just encode the whole batch
            vecs = model.encode(list(texts), convert_to_numpy=True)
            return list(vecs)

        results: list[Any] = [None] * len(texts)
        miss_indices: list[int] = []
        miss_texts: list[str] = []

        for i, t in enumerate(texts):
            cached = self.get(t, model_name)
            if cached is not None:
                results[i] = cached
            else:
                miss_indices.append(i)
                miss_texts.append(t)

        if miss_texts:
            # Encode all misses in one batch (much faster than one-by-one)
            new_vecs = model.encode(miss_texts, convert_to_numpy=True)
            for idx, text, vec in zip(miss_indices, miss_texts, new_vecs):
                results[idx] = vec
                self.put(text, model_name, vec)

        return results

    def stats(self) -> dict:
        """Return cache statistics (entry count, size in MB)."""
        try:
            count = 0
            size = 0
            for npy in self._root.rglob("*.npy"):
                count += 1
                size += npy.stat().st_size
            return {"entries": count, "size_mb": round(size / (1024 * 1024), 1)}
        except Exception:
            return {"entries": 0, "size_mb": 0.0}

    def clear(self) -> int:
        """Delete all cache entries. Returns the number of files deleted."""
        deleted = 0
        try:
            import shutil
            for model_dir in self._root.iterdir():
                if model_dir.is_dir():
                    count = sum(1 for _ in model_dir.rglob("*.npy"))
                    shutil.rmtree(model_dir)
                    deleted += count
        except Exception as exc:
            logger.debug("embed cache clear failed: %s: %s", type(exc).__name__, exc)
        return deleted


# Module-level singleton (mirrors the pattern in response_cache.py)
embed_cache = EmbedCache()


__all__ = ["EmbedCache", "embed_cache"]
