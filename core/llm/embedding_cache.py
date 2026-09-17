"""V18.2.24 (Phase 3.3): Disk-persisted embedding cache for text -> vector lookups.

Mirrors the architecture of :mod:`core.llm.response_cache` (the prompt -> response
cache) but for text -> vector. Caches embeddings keyed by
``sha256(text + model_name)`` so the same text is never re-encoded across runs.

Why this matters
----------------
The V18.2.21 conversion log showed the broken embedder making **2760+** encode
calls in a single chapter's ``content_judge`` (46 claims x ~30 summary texts
x 2 encode calls per pair). Even with a working embedder (V18.2.23 fail-safe
fix), re-encoding the same source text across re-runs is pure waste -- disk
persistence eliminates it. The cache is checked BEFORE ``model.encode()`` is
called, so cache hits skip the embedder entirely (zero network / zero GPU
time). For a 50-chapter re-conversion where the source text hasn't changed,
this turns ~138,000 encode calls into ~2,760 (one per unique text) on the
first run, then ZERO on every subsequent run.

Architecture (mirrors :mod:`core.llm.response_cache`):

  - **In-memory** ``OrderedDict[text_hash -> np.ndarray]`` (fast lookup).
  - **Disk-persisted** JSONL at ``~/.elixir/embed_cache.jsonl``
    (append-only, one JSON line per entry: ``{"key": hash, "dim": N,
    "vec": [float, ...]}``). Survives app restarts.
  - **Thread-safe** via ``threading.Lock`` (concurrent ``ThreadPoolExecutor``
    summariser workers don't corrupt the dict or the disk file).
  - **FIFO cap** default 5000 entries. Embeddings are ~1.5KB each for
    384-dim float32 (384 x 4 bytes), so 5000 = ~7.5MB in memory -- fine for
    disk (the JSONL on disk is ~20MB but that's still negligible).

Key derivation
--------------
``sha256(model_name + b"|" + text)`` -- NOT ``md5`` like response_cache.
Using sha256 because a hash collision on a cached VECTOR silently returns
the WRONG embedding (vs response_cache where a collision returns the wrong
TEXT -- both bad, but a wrong vector is harder to detect downstream). The
``b"|"`` separator prevents ``"abc"+"def"`` colliding with ``"ab"+"cdef"``.
The ``model_name`` is mixed into the key so different models
(``bge-small-en-v1.5`` vs ``all-MiniLM-L6-v2``) don't collide -- a 384-dim
bge vector and a 384-dim MiniLM vector are NOT interchangeable.

V18.2.24: Integration is opt-in via :func:`cached_encode`. The existing
callers (``content_judge``, ``keypoints_builder``,
``summarizer._semantic_dedup_bullets``) are NOT yet modified -- that's the
follow-up wiring task. This module just provides the cache + drop-in
replacement helper.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# V18.2.24: disk persistence location -- matches response_cache.py convention.
_CACHE_FILE = Path.home() / ".elixir" / "embed_cache.jsonl"

# V18.2.24: default FIFO cap. 5000 entries x ~1.5KB = ~7.5MB in memory.
# Embeddings are deterministic given (text, model), so the same vector never
# needs to be re-encoded -- 5000 unique texts covers most books comfortably.
_DEFAULT_MAX_ENTRIES = 5000


class EmbeddingCache:
    """In-memory + disk-persisted FIFO embedding cache.

    Usage::

        from core.llm.embedding_cache import embedding_cache
        vec = embedding_cache.get_or_compute(
            text, model_name,
            lambda t: model.encode([t])[0],
        )

    Or use the drop-in replacement for ``model.encode``::

        from core.llm.embedding_cache import cached_encode
        vecs = cached_encode(model, texts, model_name="bge-small-en-v1.5")
    """

    def __init__(
        self,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        persist_to_disk: bool = True,
        cache_file: str | Path | None = None,
    ) -> None:
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._max = max_entries
        self._lock = threading.Lock()
        self._persist = persist_to_disk
        # V18.2.24: allow tests to pass a tmp_path; default to the standard
        # ``~/.elixir/embed_cache.jsonl`` location. response_cache.py
        # uses a module-level constant; adding the constructor param here is
        # a minor testability improvement that doesn't change prod behavior.
        self._cache_file: Path = (
            Path(cache_file) if cache_file is not None else _CACHE_FILE
        )
        self._hits = 0
        self._misses = 0
        self._disk_loads = 0
        self._disk_writes = 0
        if self._persist:
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Key derivation
    # ------------------------------------------------------------------

    @staticmethod
    def _key(text: str, model_name: str) -> str:
        """V18.2.24: sha256(model_name + b'|' + text).

        The ``b'|'`` separator prevents the prefix-suffix collision
        (``"abc"+"def"`` vs ``"ab"+"cdef"``) that an unguarded
        ``model_name + text`` hash would suffer.
        """
        h = hashlib.sha256()
        h.update(model_name.encode("utf-8"))
        h.update(b"|")
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def get(self, text: str, model_name: str) -> np.ndarray | None:
        """Look up a cached embedding. Returns ``None`` on miss.

        Returns a **copy** of the cached vector so callers can't mutate the
        cached value. Embedding vectors are small (~1.5KB for 384-dim
        float32), so the copy is cheap.
        """
        key = self._key(text, model_name)
        with self._lock:
            if key in self._cache:
                self._hits += 1
                # V18.2.24: move_to_end keeps FIFO eviction correct -- the
                # most-recently-accessed entry is the newest, so it's
                # evicted last. (Same pattern as response_cache.py.)
                self._cache.move_to_end(key)
                return self._cache[key].copy()
            self._misses += 1
            return None

    def put(self, text: str, model_name: str, vec: np.ndarray) -> None:
        """Cache an embedding. Evicts the oldest entry if over the cap.

        V18.2.24: refuses to cache degenerate vectors (empty, all-zero, or
        NaN). The V18.2.23 fail-safe fix made ``OllamaEmbedBackend.encode``
        return zero vectors when unhealthy; caching those would poison every
        subsequent lookup with the wrong vector. Better to recompute on the
        next call (after the embedder is healthy again).
        """
        if vec is None:
            return
        arr = np.asarray(vec, dtype=np.float32)
        if arr.size == 0:
            return
        if not np.any(arr):
            # All-zero vector -- likely the fail-safe output of an unhealthy
            # embedder. Don't cache it; the next call will recompute.
            logger.debug(
                "EmbeddingCache: refusing to cache all-zero vector for "
                "text=%r model=%r (embedder may be unhealthy)",
                text[:80], model_name,
            )
            return
        if np.isnan(arr).any():
            logger.debug(
                "EmbeddingCache: refusing to cache NaN vector for text=%r model=%r",
                text[:80], model_name,
            )
            return

        key = self._key(text, model_name)
        with self._lock:
            self._cache[key] = arr
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
        if self._persist:
            self._append_to_disk(key, arr)

    def get_or_compute(
        self,
        text: str,
        model_name: str,
        compute_fn: Callable[[str], np.ndarray],
    ) -> np.ndarray:
        """Check cache; on miss call ``compute_fn(text)``, cache, return.

        This is the primary API. Callers pass a function that does the
        actual encoding (e.g. ``lambda t: model.encode([t])[0]``). The cache
        handles the lookup + storage.

        Thread-safety: the lock is **released** during ``compute_fn`` so
        other threads can serve cache hits concurrently. This means two
        threads racing on the same miss may both call ``compute_fn`` -- the
        second ``put`` simply overwrites the first. This is acceptable
        (caching is an optimization, not a correctness requirement -- both
        threads compute the same vector for the same input, so the result
        is identical). Holding the lock during ``compute_fn`` would
        serialize all encoding (defeating the ThreadPoolExecutor's purpose).
        """
        cached = self.get(text, model_name)
        if cached is not None:
            return cached
        # Miss -- compute WITHOUT holding the lock (so cache hits on other
        # texts aren't blocked), then cache the result.
        vec = compute_fn(text)
        self.put(text, model_name, vec)
        return np.asarray(vec, dtype=np.float32)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def get_many(
        self, texts: Sequence[str], model_name: str
    ) -> list[np.ndarray | None]:
        """Look up multiple texts at once. Returns a list of Optional vectors.

        Useful for pre-probing a batch before deciding which texts to
        encode. ``cached_encode`` uses this internally.
        """
        return [self.get(t, model_name) for t in texts]

    def put_many(
        self, texts: Sequence[str], model_name: str, vecs: np.ndarray
    ) -> None:
        """Cache multiple embeddings at once (e.g. from a batch encode call)."""
        vecs_arr = np.asarray(vecs, dtype=np.float32)
        if vecs_arr.ndim == 1:
            vecs_arr = vecs_arr.reshape(1, -1)
        if len(texts) != len(vecs_arr):
            raise ValueError(
                f"texts/vecs length mismatch: {len(texts)} vs {len(vecs_arr)}"
            )
        # Lengths are verified equal above; strict=False keeps the loop
        # robust if a caller passes an iterator that doesn't pre-compute length.
        for t, v in zip(texts, vecs_arr, strict=False):
            self.put(t, model_name, v)

    # ------------------------------------------------------------------
    # Disk persistence
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        """Load the disk cache into memory on startup."""
        if not self._cache_file.exists():
            return
        try:
            count = 0
            with open(self._cache_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        key = entry.get("key", "")
                        dim = int(entry.get("dim", 0))
                        vec_list = entry.get("vec", [])
                        if not key or not vec_list or dim <= 0:
                            continue
                        arr = np.array(vec_list, dtype=np.float32)
                        if arr.size != dim:
                            continue
                        # V18.2.24: skip degenerate entries on load
                        # (defensive -- if a previous run cached a
                        # degenerate vector before the put() guard existed,
                        # don't propagate it).
                        if not np.any(arr) or np.isnan(arr).any():
                            continue
                        self._cache[key] = arr
                        count += 1
                    except (json.JSONDecodeError, ValueError, TypeError):
                        continue
            # If we loaded more than max, trim to FIFO order.
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
            self._disk_loads = count
            if count > 0:
                logger.debug(
                    "Embedding cache: loaded %d entries from disk (%s)",
                    count, self._cache_file,
                )
        except Exception as exc:
            logger.debug(
                "Embedding cache disk load failed: %s: %s",
                type(exc).__name__, exc,
            )

    def _append_to_disk(self, key: str, vec: np.ndarray) -> None:
        """Append a single entry to the disk cache (JSONL append-only).

        V18.2.24: stores ``{"key": hash, "dim": N, "vec": [float, ...]}``
        per line. ``vec`` is serialized as a list of Python floats (not the
        numpy repr) so the JSONL is portable across numpy versions and
        loadable by ``json.loads`` without a custom decoder.
        """
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            flat = vec.reshape(-1)
            entry = json.dumps(
                {
                    "key": key,
                    "dim": int(flat.shape[0]),
                    "vec": [float(x) for x in flat.tolist()],
                },
                ensure_ascii=False,
            )
            with open(self._cache_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            self._disk_writes += 1
        except Exception as exc:
            logger.debug(
                "Embedding cache disk write failed: %s: %s",
                type(exc).__name__, exc,
            )

    def _flush_to_disk(self) -> None:
        """Rewrite the entire disk cache from memory (used after eviction).

        V18.2.24: the append-only file accumulates stale entries after
        evictions (the evicted entry remains in the file but is gone from
        memory). Periodically rewriting the file compacts it. This is
        currently only called by ``clear()``; a future improvement could
        trigger it after N evictions.
        """
        if not self._persist:
            return
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                lines = []
                for key, vec in self._cache.items():
                    flat = vec.reshape(-1)
                    lines.append(
                        json.dumps(
                            {
                                "key": key,
                                "dim": int(flat.shape[0]),
                                "vec": [float(x) for x in flat.tolist()],
                            },
                            ensure_ascii=False,
                        )
                    )
            self._cache_file.write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            logger.debug(
                "Embedding cache disk flush failed: %s: %s",
                type(exc).__name__, exc,
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def hits(self) -> int:
        """Number of cache hits since construction (or last ``clear()``)."""
        return self._hits

    @property
    def misses(self) -> int:
        """Number of cache misses since construction (or last ``clear()``)."""
        return self._misses

    @property
    def disk_loads(self) -> int:
        """Number of entries loaded from disk at construction."""
        return self._disk_loads

    @property
    def disk_writes(self) -> int:
        """Number of entries appended to disk since construction."""
        return self._disk_writes

    def stats(self) -> dict:
        """Return cache statistics (hits, misses, size, hit rate, disk stats).

        Mirrors the shape of :meth:`ResponseCache.stats` (hits, misses,
        size, max, hit_rate) plus the two disk counters.
        """
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max": self._max,
                "hit_rate": (self._hits / total) if total > 0 else 0.0,
                "disk_loads": self._disk_loads,
                "disk_writes": self._disk_writes,
            }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all cached embeddings (memory + disk)."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._disk_loads = 0
            self._disk_writes = 0
        # V18.2.24: matches response_cache.py's clear() pattern (try/except/pass
        # rather than contextlib.suppress, for consistency with the sibling
        # module). ruff SIM105 is intentionally suppressed here.
        if self._persist:
            try:  # noqa: SIM105
                self._cache_file.unlink(missing_ok=True)
            except Exception:
                pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


# ── Module-level singleton (shared across all embedding calls in one session) ─
# V18.2.24: constructed at import time, like response_cache. The disk load
# is cheap (returns early if the file doesn't exist), so import cost is
# negligible when no cache file is present.
embedding_cache = EmbeddingCache(
    max_entries=_DEFAULT_MAX_ENTRIES, persist_to_disk=True
)


# ── Drop-in replacement for model.encode() ──────────────────────────────────


def cached_encode(
    model: Any,
    texts: str | Sequence[str],
    model_name: str = "",
) -> np.ndarray:
    """V18.2.24: Drop-in replacement for ``model.encode(texts)`` that checks
    the cache first.

    For cache hits, returns the cached vector directly. For misses, calls
    ``model.encode(miss_texts)`` in ONE batched call (more efficient than
    per-text encoding -- Ollama's ``/api/embeddings`` is single-text per
    call, so batching misses saves N-1 round-trips), caches each result,
    and assembles the final array.

    Returns a numpy array with the **same shape** as ``model.encode(texts)``:

      - Single string input -> shape ``(dim,)``
      - List input -> shape ``(n, dim)``

    Parameters
    ----------
    model:
        Any object with an ``.encode(texts) -> np.ndarray`` method
        (``SentenceTransformer``, ``SentenceTransformerBackend``, or
        ``OllamaEmbedBackend``).
    texts:
        A single string or a sequence of strings.
    model_name:
        The model name used to derive the cache key (so different models
        don't collide). If empty, attempts to read ``model.model_name``
        (``OllamaEmbedBackend`` exposes this); falls back to ``"default"``.

    Notes
    -----
    The cache is the module-level :data:`embedding_cache` singleton. Tests
    should monkeypatch the singleton with a fresh, isolated instance.
    """
    # V18.2.24: resolve model_name from the model object if not provided.
    # OllamaEmbedBackend exposes ``.model_name``; SentenceTransformerBackend
    # wraps a HF model that doesn't have a stable name attribute, so callers
    # using the HF path should pass model_name explicitly.
    if not model_name:
        model_name = getattr(model, "model_name", "") or "default"

    # ------------------------------------------------------------------
    # Single-string input -- handle separately so we return shape (dim,)
    # to match ``model.encode("text")``.
    # ------------------------------------------------------------------
    if isinstance(texts, str):
        vec = embedding_cache.get_or_compute(
            texts,
            model_name,
            lambda t: np.asarray(model.encode(t), dtype=np.float32),
        )
        return np.asarray(vec, dtype=np.float32)

    # ------------------------------------------------------------------
    # Batch input -- return shape (n, dim).
    # ------------------------------------------------------------------
    texts_list = list(texts)
    if not texts_list:
        return np.array([], dtype=np.float32)

    # V18.2.24: de-duplicate within the call so the same text repeated N
    # times in the batch only costs one encode call. The result is
    # reassembled in original order at the end.
    unique_texts: list[str] = []
    seen: dict[str, int] = {}
    for t in texts_list:
        if t not in seen:
            seen[t] = len(unique_texts)
            unique_texts.append(t)

    # Probe cache for all unique texts (increments hits/misses).
    cached_vecs: list[np.ndarray | None] = [
        embedding_cache.get(t, model_name) for t in unique_texts
    ]
    miss_indices = [i for i, v in enumerate(cached_vecs) if v is None]
    miss_texts = [unique_texts[i] for i in miss_indices]

    if miss_texts:
        # Batch-encode all misses in ONE call (efficient for Ollama --
        # saves N-1 round-trips).
        miss_vecs_raw = model.encode(miss_texts)
        miss_vecs = np.asarray(miss_vecs_raw, dtype=np.float32)
        if miss_vecs.ndim == 1:
            # Backend returned 1-D for a single miss -- reshape to 2-D.
            miss_vecs = miss_vecs.reshape(1, -1)
        # Cache each miss result + fill in cached_vecs for assembly below.
        # miss_texts and miss_vecs are guaranteed the same length (both
        # derived from the same miss set); strict=False is safe.
        for t, v in zip(miss_texts, miss_vecs, strict=False):
            embedding_cache.put(t, model_name, v)
            cached_vecs[seen[t]] = v

    # Assemble the final array in de-duplicated order.
    dim = (
        int(cached_vecs[0].shape[0])
        if cached_vecs and cached_vecs[0] is not None
        else 0
    )
    unique_result = np.zeros((len(unique_texts), dim), dtype=np.float32)
    for i, v in enumerate(cached_vecs):
        if v is not None:
            unique_result[i] = v

    # Map back to original order (re-expanding duplicates).
    out = np.zeros((len(texts_list), dim), dtype=np.float32)
    for i, t in enumerate(texts_list):
        out[i] = unique_result[seen[t]]
    return out


__all__ = ["EmbeddingCache", "embedding_cache", "cached_encode"]
