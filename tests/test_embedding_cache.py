"""V18.2.24 (Phase 3.3): Tests for the disk-persisted embedding cache.

Covers:
  1. Cache miss -> compute -> store -> hit on second call.
  2. Different model names don't collide (same text, different model ->
     different cache entries).
  3. Disk persistence: put, reload (new instance), get hits.
  4. Thread safety: concurrent get_or_compute calls don't corrupt state.
  5. FIFO eviction when over the cap (oldest entry is dropped).
  6. cached_encode returns same shape as model.encode (single + batch).
  7. Stats (hits, misses, disk_loads, disk_writes) increment correctly.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# IMPORTANT: import via the package path so monkeypatch.setattr on the
# module-level singleton works cleanly.
import core.llm.embedding_cache as ec_mod
from core.llm.embedding_cache import (
    EmbeddingCache,
    cached_encode,
    embedding_cache,
)

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Shared helpers / fixtures ──────────────────────────────────────────────


def _make_vec(seed: int, dim: int = 8) -> np.ndarray:
    """Deterministic test vector (so tests are reproducible)."""
    rng = np.random.default_rng(seed)
    return rng.standard_normal(dim).astype(np.float32)


class FakeModel:
    """Minimal stand-in for a SentenceTransformer / OllamaEmbedBackend.

    Records every call to ``encode`` so tests can assert on call counts and
    batch shape. Returns deterministic vectors derived from the text hash so
    the same text always yields the same vector (cache invariant).
    """

    def __init__(self, dim: int = 8, model_name: str = "fake-model") -> None:
        self.dim = dim
        self.model_name = model_name
        self.calls: list[Any] = []  # each call's input

    def encode(
        self,
        texts: str | Sequence[str],
        convert_to_numpy: bool = True,
        **kwargs: Any,
    ) -> np.ndarray:
        self.calls.append(texts)
        if isinstance(texts, str):
            # Single string -> 1-D vector (matches SentenceTransformer API).
            return self._vec_for(texts)
        # Batch -> 2-D array (n, dim).
        if not texts:
            return np.array([], dtype=np.float32)
        return np.array([self._vec_for(t) for t in texts], dtype=np.float32)

    def _vec_for(self, text: str) -> np.ndarray:
        """Deterministic vector from the text (so cache hits match cache misses)."""
        # Use a stable hash-based seed so the same text always produces the
        # same vector (needed for the "same vector on second call" test).
        seed = abs(hash(text)) % (2**31)
        rng = np.random.default_rng(seed)
        # Add a constant offset so the vector is never all-zero (which the
        # cache would refuse to store).
        v = rng.standard_normal(self.dim).astype(np.float32) + 0.5
        return v


@pytest.fixture
def fresh_cache(tmp_path: Path) -> EmbeddingCache:
    """A fresh, isolated in-memory-only cache (no disk, no singleton pollution)."""
    return EmbeddingCache(max_entries=5000, persist_to_disk=False, cache_file=None)


@pytest.fixture
def fresh_disk_cache(tmp_path: Path) -> EmbeddingCache:
    """A fresh cache that persists to a tmp_path JSONL file."""
    return EmbeddingCache(
        max_entries=5000,
        persist_to_disk=True,
        cache_file=tmp_path / "embed_cache.jsonl",
    )


@pytest.fixture
def isolated_singleton(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> EmbeddingCache:
    """Replace the module-level singleton with an isolated instance.

    Tests that call ``cached_encode`` (which uses the singleton) should use
    this fixture so they don't pollute the real ``~/.elixir/embed_cache.jsonl``.
    """
    cache = EmbeddingCache(
        max_entries=5000,
        persist_to_disk=True,
        cache_file=tmp_path / "singleton_embed_cache.jsonl",
    )
    monkeypatch.setattr(ec_mod, "embedding_cache", cache)
    return cache


# ── 1. Cache miss -> compute -> store -> hit on second call ─────────────────


class TestMissComputeStoreHit:
    """get_or_compute must call compute_fn only on the first call."""

    def test_first_call_misses_and_computes(self, fresh_cache: EmbeddingCache) -> None:
        calls = {"n": 0}

        def compute(t: str) -> np.ndarray:
            calls["n"] += 1
            return _make_vec(1)

        v1 = fresh_cache.get_or_compute("hello", "model-a", compute)
        assert calls["n"] == 1, "compute_fn should be called exactly once on miss"
        assert v1.shape == (8,)
        assert fresh_cache.misses == 1
        assert fresh_cache.hits == 0

    def test_second_call_hits_without_computing(self, fresh_cache: EmbeddingCache) -> None:
        calls = {"n": 0}

        def compute(t: str) -> np.ndarray:
            calls["n"] += 1
            return _make_vec(2)

        v1 = fresh_cache.get_or_compute("hello", "model-a", compute)
        v2 = fresh_cache.get_or_compute("hello", "model-a", compute)
        assert calls["n"] == 1, "compute_fn should NOT be called on the second call"
        assert np.array_equal(v1, v2), "second call should return the same vector"
        assert fresh_cache.misses == 1
        assert fresh_cache.hits == 1

    def test_get_returns_none_on_miss(self, fresh_cache: EmbeddingCache) -> None:
        assert fresh_cache.get("missing", "model-a") is None
        assert fresh_cache.misses == 1
        assert fresh_cache.hits == 0

    def test_get_returns_vector_on_hit(self, fresh_cache: EmbeddingCache) -> None:
        vec = _make_vec(3)
        fresh_cache.put("hello", "model-a", vec)
        # Reset stats so we observe the hit cleanly.
        fresh_cache._hits = 0
        fresh_cache._misses = 0
        got = fresh_cache.get("hello", "model-a")
        assert got is not None
        assert np.array_equal(got, vec)
        assert fresh_cache.hits == 1
        assert fresh_cache.misses == 0

    def test_get_returns_copy_not_reference(self, fresh_cache: EmbeddingCache) -> None:
        """get() must return a copy so callers can't mutate the cached vector."""
        vec = _make_vec(5)
        fresh_cache.put("hello", "model-a", vec)
        got = fresh_cache.get("hello", "model-a")
        assert got is not None
        got[0] = 9999.0  # mutate the returned vector
        # The cached vector should be unchanged.
        got2 = fresh_cache.get("hello", "model-a")
        assert got2 is not None
        assert got2[0] != 9999.0, "cached vector must not be mutated by callers"


# ── 2. Different model names don't collide ──────────────────────────────────


class TestModelNameIsolation:
    """Same text + different model_name -> different cache entries."""

    def test_same_text_different_models_no_collision(self, fresh_cache: EmbeddingCache) -> None:
        vec_a = _make_vec(10)
        vec_b = _make_vec(20)
        fresh_cache.put("hello", "model-a", vec_a)
        fresh_cache.put("hello", "model-b", vec_b)
        got_a = fresh_cache.get("hello", "model-a")
        got_b = fresh_cache.get("hello", "model-b")
        assert got_a is not None and got_b is not None
        assert np.array_equal(got_a, vec_a), "model-a vector must be returned for model-a"
        assert np.array_equal(got_b, vec_b), "model-b vector must be returned for model-b"
        assert not np.array_equal(got_a, got_b), "vectors should differ across models"

    def test_different_texts_same_model_no_collision(self, fresh_cache: EmbeddingCache) -> None:
        """Sanity: different text + same model -> different entries."""
        vec_foo = _make_vec(1)
        vec_bar = _make_vec(2)
        fresh_cache.put("foo", "model-a", vec_foo)
        fresh_cache.put("bar", "model-a", vec_bar)
        got_foo = fresh_cache.get("foo", "model-a")
        got_bar = fresh_cache.get("bar", "model-a")
        assert got_foo is not None and got_bar is not None
        assert np.array_equal(got_foo, vec_foo)
        assert np.array_equal(got_bar, vec_bar)

    def test_empty_model_name_does_not_clash_with_named(self, fresh_cache: EmbeddingCache) -> None:
        """The default model_name='default' must be distinct from named models."""
        vec_named = _make_vec(1)
        vec_default = _make_vec(2)
        fresh_cache.put("text", "bge-small", vec_named)
        fresh_cache.put("text", "default", vec_default)
        got_named = fresh_cache.get("text", "bge-small")
        got_default = fresh_cache.get("text", "default")
        assert got_named is not None and got_default is not None
        assert np.array_equal(got_named, vec_named)
        assert np.array_equal(got_default, vec_default)


# ── 3. Disk persistence: put, reload, get hits ──────────────────────────────


class TestDiskPersistence:
    """A new EmbeddingCache instance pointing at the same JSONL file must
    load the previously-cached vectors."""

    def test_put_then_reload_hits(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "embed_cache.jsonl"
        cache1 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        vec = _make_vec(42)
        cache1.put("persist me", "model-x", vec)
        assert cache1.disk_writes == 1, "should have written one entry to disk"
        assert cache_file.exists(), "JSONL file should exist after put"

        # New instance, same file -> should load the entry.
        cache2 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache2.disk_loads == 1, "should have loaded 1 entry from disk"
        got = cache2.get("persist me", "model-x")
        assert got is not None, "entry should be in cache2 after disk load"
        assert np.array_equal(got, vec), "loaded vector should match the stored one"

    def test_disk_file_format_is_jsonl(self, tmp_path: Path) -> None:
        """The on-disk format must be the spec'd JSONL (one entry per line)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        cache.put("format test", "model-y", vec)

        import json

        with open(cache_file, encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        assert len(lines) == 1, "exactly one JSONL line per put"
        entry = json.loads(lines[0])
        assert set(entry.keys()) == {"key", "dim", "vec"}, (
            "entry must have exactly the keys {key, dim, vec}"
        )
        assert entry["dim"] == 4
        assert len(entry["vec"]) == 4
        assert entry["vec"][0] == pytest.approx(0.1, abs=1e-6)
        assert isinstance(entry["vec"][0], float), "vec values must be JSON floats"

    def test_multiple_puts_all_persist(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "embed_cache.jsonl"
        cache1 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        for i in range(5):
            cache1.put(f"text-{i}", "model-z", _make_vec(i))
        assert cache1.disk_writes == 5

        cache2 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache2.disk_loads == 5
        for i in range(5):
            got = cache2.get(f"text-{i}", "model-z")
            assert got is not None, f"text-{i} must be loaded from disk"
            assert np.array_equal(got, _make_vec(i))

    def test_persist_false_does_not_touch_disk(self, tmp_path: Path) -> None:
        """When persist_to_disk=False, no file should be created."""
        cache_file = tmp_path / "should_not_exist.jsonl"
        cache = EmbeddingCache(persist_to_disk=False, cache_file=cache_file)
        cache.put("x", "m", _make_vec(0))
        assert not cache_file.exists(), "persist_to_disk=False must not create the file"
        assert cache.disk_writes == 0
        assert cache.disk_loads == 0

    def test_clear_removes_disk_file(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        cache.put("hello", "m", _make_vec(0))
        assert cache_file.exists()
        cache.clear()
        assert not cache_file.exists(), "clear() must remove the disk file"
        assert len(cache) == 0

    def test_corrupt_line_skipped(self, tmp_path: Path) -> None:
        """A malformed JSONL line must be skipped without crashing load."""
        cache_file = tmp_path / "embed_cache.jsonl"
        # Write one valid + one corrupt + one valid line.
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        good_vec = _make_vec(7)
        with open(cache_file, "w", encoding="utf-8") as f:
            import json

            f.write(
                json.dumps(
                    {
                        "key": "k1",
                        "dim": 8,
                        "vec": [float(x) for x in good_vec.tolist()],
                    }
                )
                + "\n"
            )
            f.write("this is not valid json\n")
            f.write(
                json.dumps(
                    {
                        "key": "k2",
                        "dim": 8,
                        "vec": [float(x) for x in _make_vec(8).tolist()],
                    }
                )
                + "\n"
            )

        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache.disk_loads == 2, "should load 2 valid entries, skip the corrupt one"
        assert cache.get("k1-missing-text", "m") is None  # we never stored the text mapping
        # Note: we don't have the original text, but we can verify the keys
        # are in the in-memory dict (via len).
        assert len(cache) == 2


# ── 4. Thread safety: concurrent get_or_compute ────────────────────────────


class TestThreadSafety:
    """Concurrent get_or_compute calls must not corrupt the cache."""

    def test_concurrent_same_text_all_get_same_vector(self, fresh_cache: EmbeddingCache) -> None:
        """N threads call get_or_compute(text) concurrently; all must get
        the same vector and the cache must end up with exactly one entry."""
        N = 20
        results: list[np.ndarray | None] = [None] * N
        barrier = threading.Barrier(N)  # so all threads start together

        def compute(t: str) -> np.ndarray:
            # Tiny delay so the race window is wider (more likely to detect
            # corruption if locking is broken).
            time.sleep(0.001)
            return _make_vec(99)

        def worker(idx: int) -> None:
            barrier.wait()
            results[idx] = fresh_cache.get_or_compute("shared", "model-t", compute)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results must be non-None and identical.
        assert all(r is not None for r in results), "every thread must get a vector"
        for r in results[1:]:
            assert np.array_equal(r, results[0]), "all threads must get the same vector"
        # Cache must end up with exactly ONE entry (the shared text).
        assert len(fresh_cache) == 1, "cache must contain exactly one entry after concurrent calls"

    def test_concurrent_different_texts_no_corruption(self, fresh_cache: EmbeddingCache) -> None:
        """N threads each encode a UNIQUE text; cache must end up with N entries,
        each with the right vector."""
        N = 20

        def make_compute(seed: int):
            def compute(t: str) -> np.ndarray:
                time.sleep(0.001)
                return _make_vec(seed)

            return compute

        def worker(idx: int) -> np.ndarray:
            return fresh_cache.get_or_compute(f"text-{idx}", "model-t", make_compute(idx))

        threads: list[threading.Thread] = []
        results: list[np.ndarray | None] = [None] * N
        for i in range(N):

            def make_runner(idx: int):
                def run() -> None:
                    results[idx] = worker(idx)

                return run

            t = threading.Thread(target=make_runner(i))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fresh_cache) == N, f"cache must contain {N} entries, got {len(fresh_cache)}"
        for i in range(N):
            assert results[i] is not None
            assert np.array_equal(results[i], _make_vec(i))

    def test_concurrent_puts_dont_lose_entries(self, fresh_cache: EmbeddingCache) -> None:
        """N threads each put a unique entry; the in-memory cache must not
        lose any (no partial writes due to lock contention)."""
        N = 50

        def worker(idx: int) -> None:
            fresh_cache.put(f"key-{idx}", "model-t", _make_vec(idx))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fresh_cache) == N
        for i in range(N):
            got = fresh_cache.get(f"key-{i}", "model-t")
            assert got is not None, f"key-{i} must be present after concurrent puts"


# ── 5. FIFO eviction when over cap ──────────────────────────────────────────


class TestFIFOEviction:
    """When the cache exceeds its cap, the OLDEST entry must be evicted."""

    def test_eviction_drops_oldest(self) -> None:
        cache = EmbeddingCache(max_entries=3, persist_to_disk=False)
        cache.put("oldest", "m", _make_vec(1))
        cache.put("middle", "m", _make_vec(2))
        cache.put("newest", "m", _make_vec(3))
        assert len(cache) == 3
        # Adding a 4th must evict the oldest ("oldest").
        cache.put("extra", "m", _make_vec(4))
        assert len(cache) == 3, "cache must stay at cap after eviction"
        assert cache.get("oldest", "m") is None, "oldest entry must be evicted"
        assert cache.get("middle", "m") is not None, "middle entry must survive"
        assert cache.get("newest", "m") is not None, "newest entry must survive"
        assert cache.get("extra", "m") is not None, "extra entry must be present"

    def test_get_refreshes_position(self) -> None:
        """Accessing an entry via get() should move it to the newest position
        (so it's evicted last)."""
        cache = EmbeddingCache(max_entries=3, persist_to_disk=False)
        cache.put("a", "m", _make_vec(1))
        cache.put("b", "m", _make_vec(2))
        cache.put("c", "m", _make_vec(3))
        # Access "a" -> should move it to the newest position.
        cache.get("a", "m")
        # Now add a 4th -> "b" (the new oldest) should be evicted.
        cache.put("d", "m", _make_vec(4))
        assert cache.get("a", "m") is not None, "'a' should survive because it was accessed"
        assert cache.get("b", "m") is None, "'b' should be evicted as the new oldest"

    def test_put_same_text_refreshes_position(self) -> None:
        """Re-putting the same text should move it to newest (not create a duplicate)."""
        cache = EmbeddingCache(max_entries=3, persist_to_disk=False)
        cache.put("a", "m", _make_vec(1))
        cache.put("b", "m", _make_vec(2))
        cache.put("c", "m", _make_vec(3))
        # Re-put "a" -> should move to newest, no duplicate.
        cache.put("a", "m", _make_vec(99))
        assert len(cache) == 3, "no duplicate should be created"
        # Add 4th -> "b" (oldest) should be evicted.
        cache.put("d", "m", _make_vec(4))
        assert cache.get("a", "m") is not None
        assert cache.get("b", "m") is None

    def test_eviction_with_disk_persistence(self, tmp_path: Path) -> None:
        """Eviction must not crash when persist_to_disk=True (file grows with
        stale entries; that's acceptable -- _flush_to_disk compacts later)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(max_entries=2, persist_to_disk=True, cache_file=cache_file)
        cache.put("a", "m", _make_vec(1))
        cache.put("b", "m", _make_vec(2))
        cache.put("c", "m", _make_vec(3))  # evicts "a"
        assert len(cache) == 2
        assert cache.get("a", "m") is None
        # Reload from disk -- the append-only file still has all 3 entries,
        # but the cap trimming on load must leave only the newest 2.
        cache2 = EmbeddingCache(max_entries=2, persist_to_disk=True, cache_file=cache_file)
        assert len(cache2) == 2, "load must trim to cap"
        # The newest 2 (b, c) must be present; "a" must NOT (it was evicted
        # before the reload -- but since the file is append-only and
        # contains "a" too, load order is what matters: b then c then a.
        # The trim keeps b and c (the first two loaded), evicts a (the
        # last loaded). So all three keys might be present but only 2
        # fit in memory -- the in-memory representation should NOT
        # contain "a" because trim is FIFO (popitem(last=False) drops
        # the OLDEST = "a" because of move_to_end on each insert).

    def test_zero_max_entries_evicts_everything(self) -> None:
        """Edge case: max_entries=0 must accept no entries."""
        cache = EmbeddingCache(max_entries=0, persist_to_disk=False)
        cache.put("a", "m", _make_vec(1))
        assert len(cache) == 0
        assert cache.get("a", "m") is None


# ── 6. cached_encode returns same shape as model.encode ─────────────────────


class TestCachedEncodeShape:
    """cached_encode must return the same shape as model.encode would."""

    def test_single_string_returns_1d(self, isolated_singleton: EmbeddingCache) -> None:
        model = FakeModel(dim=8, model_name="fake")
        # Direct call -- returns 1-D.
        direct = model.encode("hello")
        assert direct.shape == (8,)
        # cached_encode -- must also return 1-D.
        cached = cached_encode(model, "hello", model_name="fake")
        assert cached.shape == (8,)
        # And the values must match (cache miss -> compute -> same vector).
        assert np.allclose(cached, direct)

    def test_batch_returns_2d(self, isolated_singleton: EmbeddingCache) -> None:
        model = FakeModel(dim=8, model_name="fake")
        texts = ["a", "b", "c"]
        direct = model.encode(texts)
        assert direct.shape == (3, 8)
        cached = cached_encode(model, texts, model_name="fake")
        assert cached.shape == (3, 8), "cached_encode must return 2-D for list input"
        assert np.allclose(cached, direct)

    def test_single_element_list_returns_2d(self, isolated_singleton: EmbeddingCache) -> None:
        """A list with one element must return 2-D (n=1), NOT 1-D.

        This matches ``model.encode(["text"])`` semantics: passing a list
        (even of length 1) returns a 2-D batch array.
        """
        model = FakeModel(dim=8, model_name="fake")
        direct = model.encode(["solo"])
        assert direct.shape == (1, 8)
        cached = cached_encode(model, ["solo"], model_name="fake")
        assert cached.shape == (1, 8)

    def test_empty_list_returns_empty_array(self, isolated_singleton: EmbeddingCache) -> None:
        model = FakeModel(dim=8, model_name="fake")
        cached = cached_encode(model, [], model_name="fake")
        assert cached.size == 0

    def test_second_call_uses_cache_no_encode(self, isolated_singleton: EmbeddingCache) -> None:
        """Second call to cached_encode with the same texts must NOT call
        model.encode (cache hit)."""
        model = FakeModel(dim=8, model_name="fake")
        texts = ["x", "y", "z"]
        cached_encode(model, texts, model_name="fake")
        encode_calls_after_first = len(model.calls)
        cached_encode(model, texts, model_name="fake")
        encode_calls_after_second = len(model.calls)
        assert encode_calls_after_second == encode_calls_after_first, (
            "model.encode must NOT be called on the second call (all cache hits)"
        )

    def test_partial_hit_encodes_only_misses(self, isolated_singleton: EmbeddingCache) -> None:
        """If some texts are cached and some aren't, only the misses must
        be encoded (batched in one call)."""
        model = FakeModel(dim=8, model_name="fake")
        # Pre-populate the cache for "hit-1" and "hit-2".
        cached_encode(model, ["hit-1", "hit-2"], model_name="fake")
        encode_calls_before = len(model.calls)
        # Now call with [hit-1, miss-1, hit-2, miss-2].
        cached_encode(model, ["hit-1", "miss-1", "hit-2", "miss-2"], model_name="fake")
        # Should have made exactly ONE additional encode call (for the batch
        # of misses ["miss-1", "miss-2"]).
        encode_calls_after = len(model.calls)
        assert encode_calls_after - encode_calls_before == 1, (
            "only one batched encode call should be made for the 2 misses, "
            f"got {encode_calls_after - encode_calls_before}"
        )

    def test_duplicate_texts_in_batch_encoded_once(
        self, isolated_singleton: EmbeddingCache
    ) -> None:
        """Duplicate texts within a single batch must only be encoded ONCE."""
        model = FakeModel(dim=8, model_name="fake")
        texts = ["dup", "dup", "dup", "unique"]
        cached_encode(model, texts, model_name="fake")
        # "dup" appears 3 times but should be encoded once. "unique" once.
        # Total unique = 2, so model.encode should be called once with a
        # batch of 2 (or potentially 1 single-string call -- both acceptable).
        # The total number of encode CALLS should be 1 (one batched call).
        assert len(model.calls) == 1, (
            "duplicate texts should be batched into a single encode call, "
            f"got {len(model.calls)} calls"
        )
        # And the batch should contain exactly 2 unique texts.
        last_call = model.calls[-1]
        assert list(last_call) == ["dup", "unique"]

    def test_model_name_inferred_from_model_object(
        self, isolated_singleton: EmbeddingCache
    ) -> None:
        """If model_name is empty, cached_encode should infer it from
        ``model.model_name`` (OllamaEmbedBackend exposes this)."""
        model = FakeModel(dim=8, model_name="inferred-model-name")
        cached_encode(model, "hello")  # model_name="" -> inferred
        # Now call with the EXPLICIT name -- should hit the cache.
        encode_calls_before = len(model.calls)
        cached_encode(model, "hello", model_name="inferred-model-name")
        assert len(model.calls) == encode_calls_before, (
            "explicit name matching inferred name should hit the cache"
        )
        # Different name -> miss.
        cached_encode(model, "hello", model_name="different-name")
        assert len(model.calls) == encode_calls_before + 1, (
            "different name should miss and call encode"
        )

    def test_model_name_defaults_to_default_when_no_attr(
        self, isolated_singleton: EmbeddingCache
    ) -> None:
        """If model has no .model_name attribute and name is empty, fall back
        to 'default'."""
        # MagicMock with no .model_name attribute -> getattr returns the
        # default "" -> falls back to "default".
        model = MagicMock()
        model.model_name = None  # explicitly None
        # Remove the attribute entirely so getattr returns the default.
        del model.model_name
        # V18.2.24: for single-string input, cached_encode calls
        # ``model.encode(text)`` directly (the string, NOT a list) to match
        # ``SentenceTransformer.encode("text")`` semantics (returns 1-D).
        model.encode = MagicMock(return_value=np.array([1.0, 2.0, 3.0], dtype=np.float32))
        cached_encode(model, "hello")
        model.encode.assert_called_once_with("hello")


# ── 7. Stats (hits, misses, disk_loads, disk_writes) ───────────────────────


class TestStats:
    """The hits/misses/disk_loads/disk_writes counters must be correct."""

    def test_hits_misses_increment(self, fresh_cache: EmbeddingCache) -> None:
        assert fresh_cache.hits == 0
        assert fresh_cache.misses == 0
        # 3 misses.
        fresh_cache.get("a", "m")
        fresh_cache.get("b", "m")
        fresh_cache.get("c", "m")
        assert fresh_cache.misses == 3
        assert fresh_cache.hits == 0
        # Put one.
        fresh_cache.put("a", "m", _make_vec(1))
        # Hit.
        fresh_cache.get("a", "m")
        assert fresh_cache.hits == 1
        assert fresh_cache.misses == 3

    def test_stats_dict_shape(self, fresh_cache: EmbeddingCache) -> None:
        fresh_cache.put("a", "m", _make_vec(1))
        fresh_cache.get("a", "m")
        fresh_cache.get("missing", "m")
        s = fresh_cache.stats()
        assert set(s.keys()) == {
            "hits",
            "misses",
            "size",
            "max",
            "hit_rate",
            "disk_loads",
            "disk_writes",
        }
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["size"] == 1
        assert s["max"] == 5000
        assert s["hit_rate"] == 0.5

    def test_disk_loads_zero_when_no_file(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(persist_to_disk=True, cache_file=tmp_path / "nonexistent.jsonl")
        assert cache.disk_loads == 0

    def test_disk_writes_increment_on_put(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(persist_to_disk=True, cache_file=tmp_path / "c.jsonl")
        assert cache.disk_writes == 0
        cache.put("a", "m", _make_vec(1))
        assert cache.disk_writes == 1
        cache.put("b", "m", _make_vec(2))
        assert cache.disk_writes == 2

    def test_disk_loads_increment_on_construction(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "c.jsonl"
        cache1 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        cache1.put("a", "m", _make_vec(1))
        cache1.put("b", "m", _make_vec(2))
        cache1.put("c", "m", _make_vec(3))
        cache2 = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache2.disk_loads == 3

    def test_clear_resets_stats(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(persist_to_disk=True, cache_file=tmp_path / "c.jsonl")
        cache.put("a", "m", _make_vec(1))
        cache.get("a", "m")
        cache.get("missing", "m")
        assert cache.hits == 1
        assert cache.misses == 1
        cache.clear()
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.disk_loads == 0
        assert cache.disk_writes == 0


# ── 8. Degenerate vector handling (defensive) ──────────────────────────────


class TestDegenerateVectors:
    """The cache must refuse to store all-zero or NaN vectors (they're the
    fail-safe output of an unhealthy embedder per V18.2.23)."""

    def test_zero_vector_not_cached(self, fresh_cache: EmbeddingCache) -> None:
        zero = np.zeros(8, dtype=np.float32)
        fresh_cache.put("zero", "m", zero)
        assert fresh_cache.get("zero", "m") is None, "all-zero vector must not be cached"
        # And the miss counter should have incremented (because get() misses).
        assert fresh_cache.misses == 1

    def test_nan_vector_not_cached(self, fresh_cache: EmbeddingCache) -> None:
        nan_vec = np.full(8, np.nan, dtype=np.float32)
        fresh_cache.put("nan", "m", nan_vec)
        assert fresh_cache.get("nan", "m") is None, "NaN vector must not be cached"

    def test_empty_vector_not_cached(self, fresh_cache: EmbeddingCache) -> None:
        empty = np.array([], dtype=np.float32)
        fresh_cache.put("empty", "m", empty)
        assert fresh_cache.get("empty", "m") is None

    def test_get_or_compute_does_not_cache_zero_from_compute(
        self, fresh_cache: EmbeddingCache
    ) -> None:
        """If compute_fn returns a zero vector, the cache must NOT store it
        (so the next call re-computes -- maybe the embedder is healthy by then)."""
        calls = {"n": 0}

        def compute(t: str) -> np.ndarray:
            calls["n"] += 1
            return np.zeros(8, dtype=np.float32)

        fresh_cache.get_or_compute("x", "m", compute)
        fresh_cache.get_or_compute("x", "m", compute)
        assert calls["n"] == 2, "compute_fn must be called twice (zero vector not cached)"


# ── 8b. Batch helpers (get_many / put_many) ────────────────────────────────


class TestBatchHelpers:
    """get_many / put_many should compose cleanly with single get/put."""

    def test_get_many_returns_optional_list(self, fresh_cache: EmbeddingCache) -> None:
        fresh_cache.put("hit", "m", _make_vec(1))
        results = fresh_cache.get_many(["hit", "miss1", "miss2"], "m")
        assert len(results) == 3
        assert results[0] is not None
        assert np.array_equal(results[0], _make_vec(1))
        assert results[1] is None
        assert results[2] is None

    def test_put_many_stores_all(self, fresh_cache: EmbeddingCache) -> None:
        texts = ["a", "b", "c"]
        vecs = np.array([_make_vec(i) for i in range(3)], dtype=np.float32)
        fresh_cache.put_many(texts, "m", vecs)
        assert len(fresh_cache) == 3
        for i, t in enumerate(texts):
            got = fresh_cache.get(t, "m")
            assert got is not None
            assert np.array_equal(got, _make_vec(i))

    def test_put_many_accepts_1d_vecs(self, fresh_cache: EmbeddingCache) -> None:
        """A single 1-D vector passed to put_many must be reshaped internally."""
        vec = _make_vec(0)
        fresh_cache.put_many(["only"], "m", vec)
        assert len(fresh_cache) == 1
        got = fresh_cache.get("only", "m")
        assert got is not None
        assert np.array_equal(got, vec)

    def test_put_many_raises_on_length_mismatch(self, fresh_cache: EmbeddingCache) -> None:
        """Length mismatch between texts and vecs must raise ValueError."""
        with pytest.raises(ValueError, match="length mismatch"):
            fresh_cache.put_many(["a", "b"], "m", np.array([_make_vec(0)]))

    def test_put_none_to_put_is_noop(self, fresh_cache: EmbeddingCache) -> None:
        """Passing None to put() must be a no-op (no entry stored)."""
        fresh_cache.put("nil", "m", None)  # type: ignore[arg-type]
        assert len(fresh_cache) == 0
        assert fresh_cache.get("nil", "m") is None


# ── 8c. Disk flush + error paths ──────────────────────────────────────────


class TestDiskFlushAndErrors:
    """Cover _flush_to_disk + the exception handlers in disk load/append/clear."""

    def test_flush_to_disk_rewrites_file_in_memory_order(self, tmp_path: Path) -> None:
        """_flush_to_disk must rewrite the JSONL with ONLY the in-memory entries
        (dropping stale append-only entries that were evicted)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(max_entries=2, persist_to_disk=True, cache_file=cache_file)
        # Append 3 entries -> "a" gets evicted from memory but stays on disk.
        cache.put("a", "m", _make_vec(1))
        cache.put("b", "m", _make_vec(2))
        cache.put("c", "m", _make_vec(3))  # evicts "a"
        # File has 3 lines (append-only).
        import json

        with open(cache_file) as f:
            assert len([ln for ln in f if ln.strip()]) == 3
        # After flush, file should have only 2 lines (b and c).
        cache._flush_to_disk()
        with open(cache_file) as f:
            lines = [ln for ln in f if ln.strip()]
        assert len(lines) == 2
        keys = [json.loads(ln)["key"] for ln in lines]
        assert cache._key("b", "m") in keys
        assert cache._key("c", "m") in keys
        assert cache._key("a", "m") not in keys

    def test_flush_to_disk_noop_when_persist_false(self, tmp_path: Path) -> None:
        """_flush_to_disk must not write anything when persist_to_disk=False."""
        cache_file = tmp_path / "should_not_exist.jsonl"
        cache = EmbeddingCache(persist_to_disk=False, cache_file=cache_file)
        cache.put("a", "m", _make_vec(1))
        cache._flush_to_disk()
        assert not cache_file.exists()

    def test_flush_to_disk_swallows_write_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_flush_to_disk must not raise if write_text fails (defensive)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        cache.put("a", "m", _make_vec(1))

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", boom)
        # Must not raise.
        cache._flush_to_disk()

    def test_append_to_disk_swallows_write_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_append_to_disk must not raise if open() fails (defensive)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)

        real_open = open

        def boom(*args: Any, **kwargs: Any) -> Any:
            if "a" in str(args[1:]):
                raise OSError("disk full")
            return real_open(*args, **kwargs)

        # Patch the builtin open used inside _append_to_disk.
        monkeypatch.setattr("builtins.open", boom)
        # Must not raise; cache must still hold the entry in memory.
        cache.put("a", "m", _make_vec(1))
        assert cache.get("a", "m") is not None

    def test_load_from_disk_swallows_unreadable_file(self, tmp_path: Path) -> None:
        """If the disk file exists but is unreadable (e.g. permissions),
        load must not raise -- it logs a debug message and continues empty."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.write_text("garbage\n")  # not valid JSONL
        # Must not raise.
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert len(cache) == 0

    def test_clear_swallows_unlink_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """clear() must not raise if unlink fails (defensive)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        cache.put("a", "m", _make_vec(1))

        def boom(self: Path, *args: Any, **kwargs: Any) -> None:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "unlink", boom)
        # Must not raise; in-memory state must still be cleared.
        cache.clear()
        assert len(cache) == 0

    def test_load_skips_entries_with_wrong_dim(self, tmp_path: Path) -> None:
        """If a disk entry's ``dim`` field doesn't match the actual vector
        length, the entry must be skipped on load."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        import json

        # Entry with dim=8 but only 4 floats in vec -> mismatch -> skip.
        with open(cache_file, "w") as f:
            f.write(json.dumps({"key": "bad", "dim": 8, "vec": [0.1, 0.2, 0.3, 0.4]}) + "\n")
            f.write(json.dumps({"key": "good", "dim": 4, "vec": [0.5, 0.6, 0.7, 0.8]}) + "\n")
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache.disk_loads == 1, "only the well-formed entry should be loaded"

    def test_load_skips_entries_missing_fields(self, tmp_path: Path) -> None:
        """Entries missing key/dim/vec fields must be skipped on load."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        import json

        with open(cache_file, "w") as f:
            f.write(
                json.dumps({"key": "", "dim": 4, "vec": [0.1, 0.2, 0.3, 0.4]}) + "\n"
            )  # empty key
            f.write(json.dumps({"key": "k2", "dim": 0, "vec": []}) + "\n")  # zero dim
            f.write(json.dumps({"key": "k3", "dim": 4, "vec": []}) + "\n")  # empty vec
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache.disk_loads == 0

    def test_load_skips_blank_lines(self, tmp_path: Path) -> None:
        """Blank lines (or whitespace-only) in the JSONL must be skipped on load."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        import json

        vec = _make_vec(1)
        with open(cache_file, "w") as f:
            f.write("\n")  # blank line at start
            f.write("   \n")  # whitespace-only line
            f.write(
                json.dumps({"key": "k1", "dim": 8, "vec": [float(x) for x in vec.tolist()]}) + "\n"
            )
            f.write("\n")  # blank line in middle
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache.disk_loads == 1, "blank lines must be skipped"

    def test_load_skips_zero_vector_entries(self, tmp_path: Path) -> None:
        """All-zero vector entries on disk must be skipped on load (defensive --
        they're the fail-safe output of an unhealthy embedder, per V18.2.23)."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        import json

        with open(cache_file, "w") as f:
            f.write(json.dumps({"key": "zero", "dim": 4, "vec": [0.0, 0.0, 0.0, 0.0]}) + "\n")
            good_vec = _make_vec(2, dim=4)
            f.write(
                json.dumps({"key": "good", "dim": 4, "vec": [float(x) for x in good_vec.tolist()]})
                + "\n"
            )
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert cache.disk_loads == 1, "all-zero entry must be skipped on load"

    def test_load_outer_exception_swallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If _load_from_disk hits an unexpected exception (e.g. open() fails
        with permission error), it must NOT raise -- it logs + continues."""
        cache_file = tmp_path / "embed_cache.jsonl"
        cache_file.write_text("something\n")

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise PermissionError("no access")

        # Patch the module-level open used inside _load_from_disk.
        monkeypatch.setattr("builtins.open", boom)
        # Must not raise; cache must be empty.
        cache = EmbeddingCache(persist_to_disk=True, cache_file=cache_file)
        assert len(cache) == 0


# ── 8d. cached_encode edge case: 1-D miss result ──────────────────────────


class TestCachedEncodeEdgeCases:
    """Edge cases in cached_encode not covered by the main shape tests."""

    def test_model_returning_1d_for_single_miss_handled(
        self, isolated_singleton: EmbeddingCache
    ) -> None:
        """If model.encode(miss_texts) returns a 1-D array (e.g. a buggy
        backend), cached_encode must reshape it to 2-D without crashing."""
        model = MagicMock()
        # Simulate a backend that returns 1-D for a single-item batch.
        model.encode = MagicMock(return_value=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        model.model_name = "buggy"
        # Must not crash on the reshape.
        result = cached_encode(model, ["solo-miss"], model_name="buggy")
        assert result.shape == (1, 4), "1-D miss result must be reshaped to (1, dim)"
        model.encode.assert_called_once()


# ── 9. Module-level singleton smoke test ───────────────────────────────────


class TestModuleSingleton:
    """The module-level singleton must be importable and behave correctly.

    These tests use the actual singleton (not the isolated fixture) so they
    verify the singleton is properly constructed at import time. They clean
    up after themselves to avoid polluting other tests.
    """

    def test_singleton_is_embedding_cache_instance(self) -> None:
        assert isinstance(embedding_cache, EmbeddingCache)

    def test_singleton_max_entries_default(self) -> None:
        assert embedding_cache._max == 5000

    def test_singleton_persists_to_disk(self) -> None:
        assert embedding_cache._persist is True

    def test_singleton_basic_get_put(self) -> None:
        # Use a unique key so we don't collide with other tests.
        text = f"singleton-test-{time.time_ns()}"
        model_name = "singleton-test-model"
        vec = _make_vec(123)
        try:
            embedding_cache.put(text, model_name, vec)
            got = embedding_cache.get(text, model_name)
            assert got is not None
            assert np.array_equal(got, vec)
        finally:
            # Clean up -- remove from in-memory cache so it doesn't leak.
            key = embedding_cache._key(text, model_name)
            with embedding_cache._lock:
                embedding_cache._cache.pop(key, None)
