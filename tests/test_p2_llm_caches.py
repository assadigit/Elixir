"""Phase 2 (Test-Net Deepening) — on-disk cache: ``response_cache``.

Baseline: ``response_cache.py`` 51/110 missed (54%).

Hermetic: the ``response_cache`` module's ``_CACHE_FILE`` global is
monkeypatched to a tmp path BEFORE any ``ResponseCache`` is built — the
module-level singleton reads the real ``~/.elixir/response_cache.jsonl`` at
import time, but no test here touches that singleton, and every instance we
build points at the tmp file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.llm.response_cache as response_cache_module
from core.llm.response_cache import ResponseCache

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
