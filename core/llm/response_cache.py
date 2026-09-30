"""V10.33.0 (Sprint 5.3): Prompt-response semantic cache for LLM calls.
V10.36.0: Added disk persistence so the cache survives app restarts.
V18.20.4.8 (P6 / O-a8): max_tokens added to the cache key (fixes W-a9 —
the old key let a call with a larger max_tokens return a response that
was generated and cached under a smaller cap: silently truncated).

Caches LLM responses keyed by ``hash(prompt + model + temperature +
max_tokens)`` so that repeated calls with the same prompt skip the LLM
entirely.  This is especially valuable for:

  - **Re-summarization**: re-running a conversion after a settings change
    hits the cache for every unchanged chapter (saves hours).
  - **Gap-fill reprompts**: the same concept-gap prompt across runs.
  - **Conservative-mode A/B testing**: comparing normal vs conservative
    output re-uses the LLM responses for unchanged chapters.

V10.36.0: The cache is now **disk-persisted** — it survives app restarts.
On startup, the disk cache is loaded into memory.  On every ``put()``,
the entry is also written to disk (append-only JSONL at
``~/.elixir/response_cache.jsonl``).  The disk cache has the same
FIFO cap as the in-memory cache (1000 entries).

Thread-safety: the cache uses a lock so concurrent workers (ThreadPoolExecutor)
don't corrupt the dict or the disk file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_FILE = Path.home() / ".elixir" / "response_cache.jsonl"


class ResponseCache:
    """In-memory + disk-persisted FIFO LLM response cache.

    Usage::

        from core.llm.response_cache import response_cache
        cached = response_cache.get(prompt, model, temperature, max_tokens)
        if cached is not None:
            return cached
        response = call_llm(prompt, model, temperature)
        response_cache.put(prompt, model, temperature, response, max_tokens)
        return response
    """

    def __init__(self, max_entries: int = 1000, persist_to_disk: bool = True) -> None:
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._max = max_entries
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._persist = persist_to_disk
        self._disk_dirty = False
        # Phase 6.4 (V0.19): periodic hit-rate instrumentation — every
        # ``_PERIODIC_EVERY`` lookups a one-line INFO summary lands in the
        # log so a long conversion's cache behavior is visible MID-run,
        # not only at the end-of-book summary (book_outer logs that one).
        self._lookups = 0
        if self._persist:
            self._load_from_disk()

    def _key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        """Build a cache key from prompt + model + temperature + max_tokens.

        V18.20.4.8 (P6 / O-a8, fixes W-a9): max_tokens is part of the key.
        The old key (prompt+model+temperature) let a call with
        max_tokens=6144 return a response that was generated (and cached)
        under max_tokens=2048 — a silently truncated response. Call sites
        vary max_tokens 2048/4096/6144/16000 for the same prompt+model+temp
        (academic-rigor floor 16000, scholar reflection 6144, etc.). Old
        disk entries simply MISS under the new key (the key hash changes)
        — safe, no migration needed. ``max_tokens=None`` (callers that
        don't track it) hashes as a distinct "default" component, so it
        can never collide with an explicit integer value.
        """
        h = hashlib.md5()  # noqa: S324 — cache key, not a security primitive
        h.update(str(model).encode())
        h.update(f"_{temperature:.2f}_".encode())
        h.update(f"_{max_tokens if max_tokens is not None else 'default'}_".encode())
        # V18.1 (O2): hash the FULL prompt — the old ``prompt[:2000]``
        # truncation caused long prompts that share their first 2000
        # chars (e.g. same chapter header + system prompt) to collide
        # and return the wrong cached response. md5 is fine here — this
        # is a cache key, not a security primitive (no collision attack
        # surface: an attacker who can control the prompt can already
        # cause cache misses, not incorrect hits — the worst case is a
        # performance degradation, not a correctness/security bug).
        # V18.2.26 (A13): added the noqa directive on the line above to
        # silence ruff/bandit security scanners that flag hashlib.md5
        # without context. (Note: this comment avoids spelling the directive
        # inline — a literal '# noqa: S324' inside a comment is itself parsed
        # as an invalid directive by newer ruff.)
        h.update(str(prompt).encode())
        return h.hexdigest()

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str | None:
        """Look up a cached response. Returns None on miss."""
        key = self._key(prompt, model, temperature, max_tokens)
        with self._lock:
            self._lookups += 1
            if self._lookups % _PERIODIC_EVERY == 0:
                _total = self._hits + self._misses
                _rate = (self._hits / _total) if _total > 0 else 0.0
                logger.info(
                    "Response cache (periodic): %d hits / %d misses (%.0f%% hit-rate), "
                    "%d/%d entries, %d evictions",
                    self._hits,
                    self._misses,
                    _rate * 100,
                    len(self._cache),
                    self._max,
                    self._evictions,
                )
            if key in self._cache:
                self._hits += 1
                self._cache.move_to_end(key)
                return self._cache[key]
            self._misses += 1
            return None

    def put(
        self,
        prompt: str,
        model: str,
        temperature: float,
        response: str,
        max_tokens: int | None = None,
    ) -> None:
        """Cache a response. Evicts the oldest entry if over the cap."""
        if not response:
            return
        key = self._key(prompt, model, temperature, max_tokens)
        with self._lock:
            self._cache[key] = response
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
                self._evictions += 1
            self._disk_dirty = True
        if self._persist:
            self._append_to_disk(key, response)

    def _load_from_disk(self) -> None:
        """Load the disk cache into memory on startup."""
        if not _CACHE_FILE.exists():
            return
        try:
            count = 0
            with open(_CACHE_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        key = entry.get("key", "")
                        resp = entry.get("response", "")
                        if key and resp:
                            self._cache[key] = resp
                            count += 1
                    except json.JSONDecodeError:
                        continue
            # If we loaded more than max, trim
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
            if count > 0:
                logger.debug("Response cache: loaded %d entries from disk", count)
        except Exception as exc:
            logger.debug("Response cache disk load failed: %s: %s", type(exc).__name__, exc)

    def _append_to_disk(self, key: str, response: str) -> None:
        """Append a single entry to the disk cache (JSONL)."""
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            entry = json.dumps({"key": key, "response": response}, ensure_ascii=False)
            with open(_CACHE_FILE, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception as exc:
            logger.debug("Response cache disk write failed: %s: %s", type(exc).__name__, exc)

    def _flush_to_disk(self) -> None:
        """Rewrite the entire disk cache from memory (used after eviction)."""
        if not self._persist:
            return
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                lines = []
                for key, resp in self._cache.items():
                    lines.append(json.dumps({"key": key, "response": resp}, ensure_ascii=False))
            _CACHE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._disk_dirty = False
        except Exception as exc:
            logger.debug("Response cache disk flush failed: %s: %s", type(exc).__name__, exc)

    def stats(self) -> dict:
        """Return cache statistics (hits, misses, size, hit rate)."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max": self._max,
                "hit_rate": (self._hits / total) if total > 0 else 0.0,
                # Phase 6.4 (V0.19): eviction count — the budget-tuning
                # signal (a busy rig with evictions > 0 is losing reusable
                # responses to the 1000-entry FIFO cap).
                "evictions": self._evictions,
            }

    def clear(self) -> None:
        """Clear all cached responses (memory + disk)."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._lookups = 0
        if self._persist:
            try:
                _CACHE_FILE.unlink(missing_ok=True)
            except OSError as _e:
                # V0.6.8 (audit B9): a failed disk-cache clear was SILENT —
                # the stale cache survived the "clear" with no trace.
                # OSError is the narrow family (permissions / FS errors);
                # a missing file is already handled by missing_ok=True.
                logger.warning(
                    "response_cache disk clear FAILED — stale cache survives (%s: %s); path=%s",
                    type(_e).__name__,
                    _e,
                    _CACHE_FILE,
                )


# Phase 6.4 (V0.19): periodic instrumentation interval (lookups between
# the mid-run INFO summaries).
_PERIODIC_EVERY = 200


# Module-level singleton (shared across all LLM calls in one session)
response_cache = ResponseCache(max_entries=1000, persist_to_disk=True)


__all__ = ["ResponseCache", "response_cache"]
