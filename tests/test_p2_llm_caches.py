"""Phase 2 (Test-Net Deepening) — on-disk caches: ``embed_cache`` + ``response_cache``.

Baselines: ``embed_cache.py`` 106/106 missed (0%), ``response_cache.py``
51/110 missed (54%).

Hermetic: ``EmbedCache`` is constructed with an explicit ``cache_root`` under
pytest's tmp dir; the ``response_cache`` module's ``_CACHE_FILE`` global is
monkeypatched to a tmp path BEFORE any ``ResponseCache`` is built — the
module-level singleton reads the real ``~/.elixir/response_cache.jsonl`` at
import time, but no test here touches that singleton, and every instance we
build points at the tmp file.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import core.llm.embed_cache as embed_cache_module
import core.llm.response_cache as response_cache_module
from core.llm.embed_cache import EmbedCache, _model_dir_name, _text_hash
from core.llm.response_cache import ResponseCache

# ════════════════════════════════════════════════════════════════════════════
# embed_cache
# ════════════════════════════════════════════════════════════════════════════


class TestEmbedCacheHelpers:
    def test_model_dir_name_slashes(self):
        assert _model_dir_name("BAAI/bge-base-en-v1.5") == "BAAI--bge-base-en-v1.5"
        assert _model_dir_name("a\\b") == "a--b"
        assert _model_dir_name("plain") == "plain"

    def test_text_hash_stable_and_truncated(self):
        h1 = _text_hash("hello")
        h2 = _text_hash("hello")
        assert h1 == h2
        assert len(h1) == 16
        assert _text_hash("world") != h1

    def test_entry_lock_reuses_same_lock(self):
        lock_a = embed_cache_module._entry_lock("k")
        lock_b = embed_cache_module._entry_lock("k")
        assert lock_a is lock_b


class TestEmbedCacheGetPut:
    """Pins CURRENT (buggy) on-disk behavior.

    SUSPECTED PRODUCTION BUG (reported, not fixed): ``put()`` builds a temp
    path with ``path.with_suffix(".npy.tmp")`` (→ ``<hash>.npy.tmp``) and
    calls ``np.save(str(tmp), ...)`` — but numpy APPENDS ``.npy`` when the
    filename doesn't end in ``.npy``, so the array is written to
    ``<hash>.npy.tmp.npy``. The subsequent ``tmp.replace(path)`` then raises
    FileNotFoundError (``<hash>.npy.tmp`` doesn't exist), which ``put()``
    swallows. Net effect: the persistent embedding cache NEVER stores
    anything; every ``put`` leaks an orphan ``.npy.tmp.npy`` file and every
    ``get`` misses. The V18.1 (O1/P2) redundant-encoding fix is defeated.
    These tests pin that behavior so the fix consciously updates them.
    """

    def test_put_writes_orphan_and_never_persists(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        cache.put("text-1", "model-a", vec)  # must not raise
        target = cache._path_for("model-a", "text-1")
        assert not target.exists()  # the intended entry was never written
        orphans = list(tmp_path.rglob("*.npy.tmp.npy"))
        assert len(orphans) == 1  # the leaked temp file
        assert cache.get("text-1", "model-a") is None  # therefore a miss

    def test_get_miss_returns_none(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        assert cache.get("never-seen", "model-a") is None

    def test_models_are_namespaced(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        cache.put("text-1", "model-a", np.ones(3, dtype=np.float32))
        assert cache.get("text-1", "model-b") is None

    def test_disabled_cache_is_noop(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        cache.set_enabled(False)
        cache.put("text-1", "model-a", np.ones(3, dtype=np.float32))
        assert cache.get("text-1", "model-a") is None
        assert cache.root == tmp_path

    def test_get_corrupt_file_returns_none(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        path = cache._path_for("model-a", "text-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"this is not a npy file")
        assert cache.get("text-1", "model-a") is None

    def test_put_failure_swallowed(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        # A non-serialisable object makes np.save raise inside put().
        cache.put("text-1", "model-a", {"not": "an array"})  # must not raise

    def test_put_disabled_skips_disk(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        cache.set_enabled(False)
        cache.put("text-1", "model-a", np.ones(2, dtype=np.float32))
        assert not any(tmp_path.rglob("*.npy"))


class _FakeModel:
    """Fake sentence-transformers-style encoder."""

    def __init__(self) -> None:
        self.batches: list = []
        self.dim = 4

    def encode(self, texts, convert_to_numpy=True, **kwargs):
        self.batches.append(list(texts) if not isinstance(texts, str) else [texts])
        if isinstance(texts, str):
            return np.full(self.dim, 1.0, dtype=np.float32)
        return np.array([np.full(self.dim, 1.0 + i, dtype=np.float32) for i, _ in enumerate(texts)])


class TestGetOrEncode:
    def test_reencodes_every_time_due_to_put_bug(self, tmp_path: Path):
        """CURRENT behavior: the disk put is a silent no-op (see the bug note
        in TestEmbedCacheGetPut), so the same text is re-encoded on every
        call — exactly the redundancy the cache was meant to remove."""
        cache = EmbedCache(cache_root=tmp_path)
        model = _FakeModel()
        vec = cache.get_or_encode(model, "hello", model_name="m")
        assert vec is not None and vec.shape == (4,)
        again = cache.get_or_encode(model, "hello", model_name="m")
        np.testing.assert_array_equal(again, vec)
        assert model.batches == [["hello"], ["hello"]]  # encoded twice (bug pin)

    def test_batch_all_misses(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        model = _FakeModel()
        vecs = cache.get_or_encode_batch(model, ["a", "b"], model_name="m")
        assert len(vecs) == 2
        assert model.batches == [["a", "b"]]
        np.testing.assert_array_equal(vecs[0], np.full(4, 1.0, dtype=np.float32))
        np.testing.assert_array_equal(vecs[1], np.full(4, 2.0, dtype=np.float32))

    def test_batch_partial_hits_only_encodes_misses(self, tmp_path: Path):
        """CURRENT behavior: because put() never persists (bug pin), a
        pre-"cached" text still counts as a miss and is re-encoded."""
        cache = EmbedCache(cache_root=tmp_path)
        cache.put("a", "m", np.full(4, 9.0, dtype=np.float32))
        model = _FakeModel()
        vecs = cache.get_or_encode_batch(model, ["a", "b"], model_name="m")
        assert len(vecs) == 2
        # Both went back to the model; "a" was NOT served from the cache.
        assert model.batches == [["a", "b"]]
        np.testing.assert_array_equal(vecs[0], np.full(4, 1.0, dtype=np.float32))

    def test_batch_disabled_fast_path(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        cache.set_enabled(False)
        model = _FakeModel()
        vecs = cache.get_or_encode_batch(model, ["a", "b"], model_name="m")
        assert len(vecs) == 2
        assert model.batches == [["a", "b"]]
        assert not any(tmp_path.rglob("*.npy"))


class TestEmbedCacheStatsAndClear:
    def test_stats_empty_root(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        assert cache.stats() == {"entries": 0, "size_mb": 0.0}

    def test_stats_counts_orphan_files(self, tmp_path: Path):
        """CURRENT behavior: stats() rglob("*.npy") counts the leaked
        ``.npy.tmp.npy`` orphan files, not real entries."""
        cache = EmbedCache(cache_root=tmp_path)
        cache.put("a", "m1", np.ones(4096, dtype=np.float32))
        cache.put("b", "m1", np.ones(4096, dtype=np.float32))
        stats = cache.stats()
        assert stats["entries"] == 2  # two orphans, not two entries
        assert stats["size_mb"] >= 0.0

    def test_stats_missing_root_returns_zero(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path / "does" / "not" / "exist")
        assert cache.stats() == {"entries": 0, "size_mb": 0.0}

    def test_clear_deletes_entries(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        cache.put("a", "m1", np.ones(4, dtype=np.float32))
        cache.put("b", "m2", np.ones(4, dtype=np.float32))
        deleted = cache.clear()
        assert deleted == 2
        assert cache.stats()["entries"] == 0

    def test_clear_empty_root_returns_zero(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path)
        assert cache.clear() == 0

    def test_get_or_encode_serves_preseeded_entry(self, tmp_path: Path):
        """A HAND-seeded .npy (written directly, bypassing the buggy put)
        IS served from the cache — the read path itself is sound."""
        import numpy.lib.format as _fmt

        cache = EmbedCache(cache_root=tmp_path)
        path = cache._path_for("model-a", "text-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            _fmt.write_array(f, np.full(4, 7.0, dtype=np.float32))
        model = _FakeModel()
        vec = cache.get_or_encode(model, "text-1", model_name="model-a")
        np.testing.assert_array_equal(vec, np.full(4, 7.0, dtype=np.float32))
        assert model.batches == []  # never reached the model

    def test_batch_serves_preseeded_entry(self, tmp_path: Path):
        """Same for the batch path: only genuine misses are encoded."""
        import numpy.lib.format as _fmt

        cache = EmbedCache(cache_root=tmp_path)
        path = cache._path_for("m", "a")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            _fmt.write_array(f, np.full(4, 5.0, dtype=np.float32))
        model = _FakeModel()
        vecs = cache.get_or_encode_batch(model, ["a", "b"], model_name="m")
        np.testing.assert_array_equal(vecs[0], np.full(4, 5.0, dtype=np.float32))
        # "b" is the FIRST (only) miss in its encode batch → 1.0, not 2.0.
        np.testing.assert_array_equal(vecs[1], np.full(4, 1.0, dtype=np.float32))
        assert model.batches == [["b"]]

    def test_stats_root_is_file_returns_zero(self, tmp_path: Path):
        not_a_dir = tmp_path / "plainfile"
        not_a_dir.write_text("hi", encoding="utf-8")
        cache = EmbedCache(cache_root=not_a_dir)
        assert cache.stats() == {"entries": 0, "size_mb": 0.0}

    def test_stats_scan_failure_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cache = EmbedCache(cache_root=tmp_path)

        def boom(self, *a, **k):
            raise OSError("scandir failed")

        monkeypatch.setattr(Path, "rglob", boom)
        assert cache.stats() == {"entries": 0, "size_mb": 0.0}

    def test_clear_missing_root_returns_zero(self, tmp_path: Path):
        cache = EmbedCache(cache_root=tmp_path / "nope")
        assert cache.clear() == 0

    def test_module_singleton_exists(self):
        assert isinstance(embed_cache_module.embed_cache, EmbedCache)


# ════════════════════════════════════════════════════════════════════════════
# response_cache
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    f = tmp_path / "response_cache.jsonl"
    monkeypatch.setattr(response_cache_module, "_CACHE_FILE", f)
    return f


class TestResponseCacheKey:
    def test_max_tokens_changes_key(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        k1 = c._key("p", "m", 0.6, 2048)
        k2 = c._key("p", "m", 0.6, 4096)
        k3 = c._key("p", "m", 0.6, None)
        assert len({k1, k2, k3}) == 3  # V18.20.4.8 (W-a9): distinct keys

    def test_temperature_and_model_in_key(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        assert c._key("p", "m1", 0.6) != c._key("p", "m2", 0.6)
        assert c._key("p", "m", 0.6) != c._key("p", "m", 0.7)

    def test_full_prompt_hashed_no_prefix_collision(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        long_a = "x" * 3000 + "A"
        long_b = "x" * 3000 + "B"
        assert c._key(long_a, "m", 0.6) != c._key(long_b, "m", 0.6)


class TestResponseCacheGetPut:
    def test_put_then_get_hit(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        assert c.get("p", "m", 0.6) is None  # miss
        c.put("p", "m", 0.6, "answer")
        assert c.get("p", "m", 0.6) == "answer"  # hit
        stats = c.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5

    def test_stats_zero_division_guard(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        assert c.stats()["hit_rate"] == 0.0

    def test_put_empty_response_ignored(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        c.put("p", "m", 0.6, "")
        assert c.get("p", "m", 0.6) is None
        assert c.stats()["size"] == 0

    def test_fifo_eviction_over_cap(self, cache_file):
        c = ResponseCache(max_entries=2, persist_to_disk=False)
        c.put("p1", "m", 0.6, "a")
        c.put("p2", "m", 0.6, "b")
        c.put("p3", "m", 0.6, "c")
        assert c.get("p1", "m", 0.6) is None  # evicted
        assert c.get("p2", "m", 0.6) == "b"
        assert c.get("p3", "m", 0.6) == "c"

    def test_get_moves_entry_to_end(self, cache_file):
        """An LRU-ish touch: hitting p1 protects it from eviction."""
        c = ResponseCache(max_entries=2, persist_to_disk=False)
        c.put("p1", "m", 0.6, "a")
        c.put("p2", "m", 0.6, "b")
        c.get("p1", "m", 0.6)  # touch → p2 is now oldest
        c.put("p3", "m", 0.6, "c")
        assert c.get("p1", "m", 0.6) == "a"
        assert c.get("p2", "m", 0.6) is None

    def test_distinct_max_tokens_do_not_collide(self, cache_file):
        """The W-a9 regression pin: a 2048-capped answer must not be served
        to a 6144-token request."""
        c = ResponseCache(persist_to_disk=False)
        c.put("p", "m", 0.6, "short answer", max_tokens=2048)
        assert c.get("p", "m", 0.6, max_tokens=6144) is None
        assert c.get("p", "m", 0.6, max_tokens=2048) == "short answer"


class TestResponseCacheDisk:
    def test_put_persists_to_disk(self, cache_file):
        c = ResponseCache()
        c.put("p", "m", 0.6, "disk answer")
        line = json.loads(cache_file.read_text(encoding="utf-8").strip())
        assert line["response"] == "disk answer"
        assert line["key"] == c._key("p", "m", 0.6)

    def test_disk_load_on_startup(self, cache_file):
        c1 = ResponseCache()
        c1.put("p", "m", 0.6, "survives restart")
        c2 = ResponseCache()
        assert c2.get("p", "m", 0.6) == "survives restart"

    def test_disk_load_skips_corrupt_and_blank_lines(self, cache_file):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            "not json\n\n"
            + json.dumps({"key": "k1", "response": "r1"})
            + "\n"
            + json.dumps({"key": "", "response": "no key"})
            + "\n"
            + json.dumps({"key": "k2", "response": ""})
            + "\n",
            encoding="utf-8",
        )
        c = ResponseCache()
        assert c.stats()["size"] == 1

    def test_disk_load_trims_over_cap(self, cache_file):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"key": f"k{i}", "response": f"r{i}"}) for i in range(10)]
        cache_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        c = ResponseCache(max_entries=3)
        assert c.stats()["size"] == 3

    def test_disk_load_unreadable_file_swallowed(self, cache_file, monkeypatch):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("{}", encoding="utf-8")

        def broken_open(*a, **k):
            raise OSError("disk on fire")

        monkeypatch.setattr("builtins.open", broken_open)
        c = ResponseCache()  # must not raise
        assert c.stats()["size"] == 0

    def test_append_to_disk_failure_swallowed(self, cache_file, monkeypatch):
        c = ResponseCache()
        monkeypatch.setattr(
            response_cache_module._CACHE_FILE.__class__,
            "mkdir",
            lambda self, *a, **k: (_ for _ in ()).throw(OSError("nope")),
        )
        c.put("p", "m", 0.6, "x")  # must not raise
        assert c.get("p", "m", 0.6) == "x"  # still in memory

    def test_flush_to_disk_rewrites_file(self, cache_file):
        c = ResponseCache()
        c.put("p1", "m", 0.6, "a")
        c.put("p2", "m", 0.6, "b")
        c._flush_to_disk()
        lines = [json.loads(x) for x in cache_file.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 2
        assert c._disk_dirty is False

    def test_flush_noop_when_not_persisting(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        c.put("p", "m", 0.6, "a")
        c._flush_to_disk()
        assert not cache_file.exists()

    def test_flush_failure_swallowed(self, cache_file, monkeypatch):
        c = ResponseCache()
        c.put("p", "m", 0.6, "a")

        def broken_write(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(cache_file.__class__, "write_text", broken_write)
        c._flush_to_disk()  # must not raise

    def test_clear_removes_memory_and_disk(self, cache_file):
        c = ResponseCache()
        c.put("p", "m", 0.6, "a")
        c.get("p", "m", 0.6)
        c.clear()
        assert c.stats() == {
            "hits": 0,
            "misses": 0,
            "size": 0,
            "max": 1000,
            "hit_rate": 0.0,
            # Phase 6.4 (V0.19): the eviction counter (budget-tuning signal)
            # resets with the rest of the stats.
            "evictions": 0,
        }
        assert not cache_file.exists()

    def test_clear_noop_when_not_persisting(self, cache_file):
        c = ResponseCache(persist_to_disk=False)
        c.put("p", "m", 0.6, "a")
        c.clear()
        assert not cache_file.exists()

    def test_clear_unlink_failure_swallowed(self, cache_file, monkeypatch):
        c = ResponseCache()
        c.put("p", "m", 0.6, "a")
        monkeypatch.setattr(
            cache_file.__class__,
            "unlink",
            lambda self, **k: (_ for _ in ()).throw(OSError("busy")),
        )
        c.clear()  # must not raise

    def test_missing_disk_file_load_is_noop(self, cache_file):
        c = ResponseCache()  # no file → no crash
        assert c.stats()["size"] == 0

    def test_module_singleton_exists(self):
        assert isinstance(response_cache_module.response_cache, ResponseCache)
