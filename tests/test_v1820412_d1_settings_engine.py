"""V18.20.4.12 (D1) — settings batch + engine-cache shutdown pins.

Two fixes, both per the V18.20.4.12 surgical batch:

- **W-c19:** ``Settings.set()`` called ``save()`` on EVERY call, and
  ``save()`` rewrites the whole settings.json (atomic write + fsync) —
  N ``set()`` calls in a loop were N full-file disk writes. NEW:
  ``Settings.batch()`` context manager defers the disk write — N set()
  calls inside the block coalesce into ONE save at the outermost exit.
  Purely ADDITIVE: set() outside a batch is byte-identical (immediate
  save), and in-memory visibility (get()/snapshot()) is unchanged even
  inside a batch.
- **W-c12:** ``core.tts.engine_cache.clear_cache()`` was a dead API
  (zero callers tree-wide) whose body was a bare ``_engines.clear()``
  — cached TTS engines were never torn down at shutdown, leaving their
  subprocesses + VRAM alive to the bitter interpreter end. Now: each
  engine is gracefully closed first (hasattr-guarded close/quit/stop/
  shutdown/_cleanup_process/_cleanup — the engines' own quit→wait→kill
  contract), never raising per engine, and the cache clear is wired into
  ``ui_qt/app.py``'s closeEvent after the worker park/join, before the
  final quit, behind a never-raise guard.

All pins are headless-safe (pure Python + source/AST slicing by NAME —
no line numbers, no PySide6 import; the rig has none).
"""

from __future__ import annotations

import ast
import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.settings import Settings  # noqa: E402

_SETTINGS = _project_root / "utils" / "settings.py"
_ENGINE_CACHE = _project_root / "core" / "tts" / "engine_cache.py"
_APP = _project_root / "ui_qt" / "app.py"


# ── helpers (headless-safe: source text + AST only, by name) ────────────────


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _classes(path: Path) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in ast.parse(_src(path)).body if isinstance(n, ast.ClassDef)}


def _method(path: Path, class_name: str, method_name: str) -> str:
    """The exact source segment of one method (located by name, no lines)."""
    src = _src(path)
    cls = _classes(path)[class_name]
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == method_name:
            return ast.get_source_segment(src, n) or ""
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _function(path: Path, fn_name: str) -> str:
    """The exact source segment of one module-level function (by name)."""
    src = _src(path)
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef) and n.name == fn_name:
            return ast.get_source_segment(src, n) or ""
    raise AssertionError(f"function {fn_name} not found in {path}")


@contextmanager
def _hermetic_settings(tmp_dir: Path):
    """Point the Settings singleton at a temp dir for the duration (the
    tests/test_v182043_p2_settings_integrity.py pattern), resetting it
    after."""
    Settings._instance = None
    Settings._test_override = None
    try:
        import unittest.mock as _mock

        with (
            _mock.patch.object(Settings, "_settings_dir", tmp_dir),
            _mock.patch.object(Settings, "_settings_file", tmp_dir / "settings.json"),
        ):
            yield
    finally:
        Settings._instance = None
        Settings._test_override = None


def _counting_save(monkeypatch, s: Settings) -> list[int]:
    """Patch s.save with a wrapper that calls the REAL save and records
    the call, so coalescing tests assert real persistence too."""
    calls: list[int] = []
    real_save = s.save

    def _counting() -> bool:
        calls.append(1)
        return real_save()

    monkeypatch.setattr(s, "save", _counting)
    return calls


def _on_disk(tmp_path: Path) -> dict:
    f = tmp_path / "settings.json"
    assert f.exists(), "batch exit must have persisted to disk"
    return json.loads(f.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# W-c19 — Settings.batch(): N set() calls coalesce into ONE save
# ═══════════════════════════════════════════════════════════════════════════


class TestWc19DefaultBehaviourUnchanged:
    """set() OUTSIDE a batch keeps the exact pre-W-c19 contract."""

    def test_set_outside_batch_saves_per_call(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            assert s.set("summarisation.model", "a:latest") is True
            assert s.set("ocr.primary_model", "b:latest") is True
            assert s.set("llm.ollama_url", "http://x:11434") is True
            assert len(calls) == 3  # one FULL save per set — unchanged

    def test_set_outside_batch_persists_immediately(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            assert s.set("summarisation.model", "immediate:latest") is True
            assert _on_disk(tmp_path)["summarisation"]["model"] == ("immediate:latest")

    def test_set_outside_batch_still_propagates_save_failure(self, tmp_path, monkeypatch):
        """W-b6 regression guard: set() returns the save() result (False on
        disk failure) outside a batch — the pre-W-c19 contract."""
        import utils.settings as settings_mod

        def _boom(*_a, **_k):
            raise OSError("disk full")

        with _hermetic_settings(tmp_path):
            s = Settings()
            monkeypatch.setattr(settings_mod, "atomic_write_json", _boom)
            result = s.set("summarisation.model", "never-persisted:latest")
            assert result is False
            # in-memory mutation still happened (fail-soft contract)
            assert s.get("summarisation.model") == "never-persisted:latest"


class TestWc19BatchCoalescing:
    def test_five_sets_inside_batch_cause_exactly_one_save(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            with s.batch():
                assert s.set("summarisation.model", "m:latest") is True
                assert s.set("ocr.primary_model", "p:latest") is True
                assert s.set("ocr.fallback_model", "f:latest") is True
                assert s.set("llm.ollama_url", "http://y:11434") is True
                assert s.set("segmentation.strategy", "fixed") is True
                assert len(calls) == 0  # deferred — no save inside the block
            assert len(calls) == 1  # ONE coalesced save at exit
            disk = _on_disk(tmp_path)
            assert disk["summarisation"]["model"] == "m:latest"
            assert disk["ocr"]["primary_model"] == "p:latest"
            assert disk["ocr"]["fallback_model"] == "f:latest"
            assert disk["llm"]["ollama_url"] == "http://y:11434"
            assert disk["segmentation"]["strategy"] == "fixed"

    def test_values_visible_mid_batch_via_get(self, tmp_path):
        """In-memory visibility inside the batch — readers must NOT wait
        for the exit save."""
        with _hermetic_settings(tmp_path):
            s = Settings()
            with s.batch():
                s.set("summarisation.model", "mid:latest")
                assert s.get("summarisation.model") == "mid:latest"
                s.set("ocr.timeout", 42)
                assert s.get("ocr.timeout") == 42
            assert s.get("summarisation.model") == "mid:latest"

    def test_snapshot_reflects_values_mid_batch(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            with s.batch():
                s.set("summarisation.model", "snap:latest")
                s.set("ocr.retries", 7)
                snap = s.snapshot()
                assert snap["summarisation"]["model"] == "snap:latest"
                assert snap["ocr"]["retries"] == 7
                # snapshot isolation is unchanged (W-c3): mutating the copy
                # must not leak into the store
                snap["ocr"]["retries"] = 999
                assert s.get("ocr.retries") == 7

    def test_later_set_wins_within_batch(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            with s.batch():
                s.set("summarisation.model", "first:latest")
                s.set("summarisation.model", "second:latest")
            assert s.get("summarisation.model") == "second:latest"
            assert _on_disk(tmp_path)["summarisation"]["model"] == ("second:latest")


class TestWc19NestedBatches:
    def test_nested_batches_one_save_at_outer_exit(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            with s.batch():
                s.set("summarisation.model", "outer:latest")
                with s.batch():
                    s.set("ocr.timeout", 11)
                    assert len(calls) == 0
                # inner exit must NOT save — still inside the outer batch
                assert len(calls) == 0
                assert s._batch_depth == 1
                s.set("ocr.retries", 3)
            assert len(calls) == 1  # exactly one save, at the OUTERMOST exit
            disk = _on_disk(tmp_path)
            assert disk["summarisation"]["model"] == "outer:latest"
            assert disk["ocr"]["timeout"] == 11
            assert disk["ocr"]["retries"] == 3

    def test_three_levels_nest(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            with s.batch():
                with s.batch():
                    with s.batch():
                        s.set("ocr.timeout", 1)
                    assert len(calls) == 0
                assert len(calls) == 0
            assert len(calls) == 1
            assert _on_disk(tmp_path)["ocr"]["timeout"] == 1


class TestWc19ExceptionSemantics:
    def test_exception_saves_partial_then_reraises(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            with pytest.raises(RuntimeError, match="boom mid-batch"):
                with s.batch():
                    s.set("summarisation.model", "partial:latest")
                    s.set("ocr.timeout", 55)
                    raise RuntimeError("boom mid-batch")
            # partial progress SURVIVES (matches set()'s per-write
            # persistence semantics) — one save fired, exception propagated
            assert len(calls) == 1
            disk = _on_disk(tmp_path)
            assert disk["summarisation"]["model"] == "partial:latest"
            assert disk["ocr"]["timeout"] == 55

    def test_exception_before_any_set_saves_nothing(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            before = (tmp_path / "settings.json").read_text(
                encoding="utf-8"
            )  # the one _load() write from __init__
            with pytest.raises(ValueError):
                with s.batch():
                    raise ValueError("nothing was set")
            assert len(calls) == 0
            assert (tmp_path / "settings.json").read_text(encoding="utf-8") == before

    def test_batch_state_clean_after_exception(self, tmp_path):
        """A failed batch must not leave depth/dirty poisoned — the NEXT
        set() outside a batch saves immediately again (default path)."""
        with _hermetic_settings(tmp_path):
            s = Settings()
            with pytest.raises(RuntimeError):
                with s.batch():
                    s.set("ocr.timeout", 1)
                    raise RuntimeError("x")
            assert s._batch_depth == 0
            assert s._batch_dirty is False
            calls = []  # noqa: F841 — asserted via real file write below
            assert s.set("ocr.timeout", 2) is True
            assert _on_disk(tmp_path)["ocr"]["timeout"] == 2


class TestWc19EmptyBatch:
    def test_empty_batch_performs_no_save(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            # NOTE: __init__/_load() writes settings.json ONCE on a fresh
            # dir (pre-existing behaviour) — snapshot it, then prove the
            # empty batch adds NOTHING on top of that.
            before = (tmp_path / "settings.json").read_text(encoding="utf-8")
            with s.batch():
                pass
            assert len(calls) == 0
            assert (tmp_path / "settings.json").read_text(encoding="utf-8") == before

    def test_nested_empty_batches_perform_no_save(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            with s.batch():
                with s.batch():
                    pass
            assert len(calls) == 0


class TestWc19HarnessInstanceDefensiveInit:
    """The codebase's tests build instances via object.__new__ (skipping
    __init__) — batch()/set() must not require the new instance attrs."""

    def test_object_new_instance_without_batch_attrs(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings.__new__(Settings)
            # the minimum state set()/save() read — NO _batch_depth/_batch_dirty
            s._lock = threading.RLock()
            s._data = {}
            assert not hasattr(s, "_batch_depth")
            assert not hasattr(s, "_batch_dirty")
            calls = _counting_save(monkeypatch, s)
            with s.batch():
                assert s.set("summarisation.model", "harness:latest") is True
                assert s.get("summarisation.model") == "harness:latest"
                assert len(calls) == 0
            assert len(calls) == 1  # getattr-defensive path still flushes
            assert _on_disk(tmp_path)["summarisation"]["model"] == ("harness:latest")
            # state materialized by the defensive path is consistent
            assert s._batch_depth == 0
            assert s._batch_dirty is False

    def test_object_new_instance_set_outside_batch_still_saves(self, tmp_path, monkeypatch):
        with _hermetic_settings(tmp_path):
            s = Settings.__new__(Settings)
            s._lock = threading.RLock()
            s._data = {}
            calls = _counting_save(monkeypatch, s)
            assert s.set("ocr.timeout", 9) is True
            assert len(calls) == 1


class TestWc19ThreadedSetters:
    def test_concurrent_set_calls_inside_batch_coalesce(self, tmp_path, monkeypatch):
        """Depth/dirty bookkeeping rides the existing RLock: set() calls
        from other threads while a batch is active are deferred too, and
        the outer exit still performs exactly ONE save."""
        with _hermetic_settings(tmp_path):
            s = Settings()
            calls = _counting_save(monkeypatch, s)
            errors: list[str] = []

            def _worker(i: int) -> None:
                try:
                    for j in range(5):
                        s.set(f"tts.thread_{i}_flag_{j}", i * 100 + j)
                except Exception as e:  # pragma: no cover — failure report
                    errors.append(f"{type(e).__name__}: {e}")

            with s.batch():
                threads = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                assert not errors
                assert len(calls) == 0  # nothing escaped the batch
            assert len(calls) == 1
            assert s.get("tts.thread_3_flag_4") == 304
            assert _on_disk(tmp_path)["tts"]["thread_0_flag_0"] == 0


class TestWc19SourcePins:
    """Headless source pins on utils/settings.py (by name, no lines)."""

    def test_batch_is_a_contextmanager(self):
        src = _strip_comments(_src(_SETTINGS))
        assert "from contextlib import contextmanager" in src
        assert "@contextmanager" in src
        assert "def batch(self)" in src

    def test_set_default_path_still_saves_immediately(self):
        body = _strip_comments(_method(_SETTINGS, "Settings", "set"))
        # the non-batch path is byte-identical: mutate, then return save()
        assert "return self.save()" in body
        # the batch path is a guarded early-return AFTER the in-memory
        # mutation — never a silent drop
        assert 'getattr(self, "_batch_depth", 0) > 0' in body
        assert "self._batch_dirty = True" in body

    def test_batch_docstring_pins_contract(self):
        body = _method(_SETTINGS, "Settings", "batch")
        for phrase in (
            "V18.20.4.12 (W-c19): defer disk writes",
            "N set() calls coalesce",
            "Nested-safe (depth counter)",
            "OUTSIDE a batch is UNCHANGED (immediate save)",
            "partial progress survives",
            "self._lock",
        ):
            assert phrase in body, f"batch() docstring lost: {phrase!r}"

    def test_batch_exit_is_try_finally(self):
        """Both the normal and the exception path must flush — the
        save-then-reraise shape."""
        body = _strip_comments(_method(_SETTINGS, "Settings", "batch"))
        assert "try:" in body
        assert "finally:" in body
        assert "self.save()" in body  # the flush

    def test_init_initialises_batch_attrs(self):
        body = _strip_comments(_method(_SETTINGS, "Settings", "__init__"))
        assert "self._batch_depth: int = 0" in body
        assert "self._batch_dirty: bool = False" in body

    def test_typing_iterator_import(self):
        src = _strip_comments(_src(_SETTINGS))
        # V0.13: UP035 auto-fix split the import — Iterator is from
        # collections.abc now (the deprecated typing alias was removed).
        assert "from typing import Any, Optional" in src
        assert "from collections.abc import Iterator" in src


# ═══════════════════════════════════════════════════════════════════════════
# W-c12 — engine_cache.clear_cache(): graceful teardown + shutdown wiring
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_engine_cache():
    """Isolate + restore the module-global engine cache around each test."""
    import core.tts.engine_cache as ec

    saved = dict(ec._engines)
    ec._engines.clear()
    try:
        yield ec
    finally:
        ec._engines.clear()
        ec._engines.update(saved)


class _FakeEngine:
    """Minimal engine double — records teardown-hook calls."""

    def __init__(self, hooks=("close",), raise_on: str | None = None):
        self.calls: list[str] = []
        self._raise_on = raise_on
        for h in hooks:
            setattr(self, h, self._make_hook(h))

    def _make_hook(self, name: str):
        def _hook():
            self.calls.append(name)
            if name == self._raise_on:
                raise RuntimeError(f"stuck {name}")

        return _hook


class TestWc12ClearCacheTeardown:
    def test_all_engines_closed_and_removed(self, clean_engine_cache):
        ec = clean_engine_cache
        good1 = _FakeEngine(hooks=("close",))
        good2 = _FakeEngine(hooks=("close",))
        ec._engines["neutts:/a.gguf"] = good1
        ec._engines["kokoro"] = good2
        assert ec.cached_engine_count() == 2

        ec.clear_cache()  # must not raise

        assert good1.calls == ["close"]
        assert good2.calls == ["close"]
        assert ec._engines == {}
        assert ec.cached_engine_count() == 0

    def test_raising_close_never_raises_and_cache_still_cleared(self, clean_engine_cache):
        ec = clean_engine_cache
        stuck = _FakeEngine(hooks=("close",), raise_on="close")
        good = _FakeEngine(hooks=("close",))
        ec._engines["qwen_tts:/q"] = stuck
        ec._engines["sherpa:v1"] = good

        ec.clear_cache()  # never-raise contract

        assert stuck.calls == ["close"]  # teardown was ATTEMPTED
        assert good.calls == ["close"]
        assert ec._engines == {}

    def test_engine_without_any_teardown_hook_is_dropped(self, clean_engine_cache):
        ec = clean_engine_cache
        bare = object()  # no close/quit/stop/shutdown/_cleanup* at all
        ec._engines["plain"] = bare
        ec.clear_cache()  # must not raise
        assert ec._engines == {}

    def test_private_cleanup_hooks_are_honoured(self, clean_engine_cache):
        """The REAL engines expose only private hooks (NeuTTS
        ``_cleanup_process``; Qwen/VibeVoice/Sherpa ``_cleanup``) — those
        must be called, not just the public names."""
        ec = clean_engine_cache
        neutts_like = _FakeEngine(hooks=("_cleanup_process",))
        qwen_like = _FakeEngine(hooks=("_cleanup",))
        ec._engines["neutts:/n.gguf"] = neutts_like
        ec._engines["qwen_tts:/m"] = qwen_like
        ec.clear_cache()
        assert neutts_like.calls == ["_cleanup_process"]
        assert qwen_like.calls == ["_cleanup"]

    def test_first_hook_wins_no_double_teardown(self, clean_engine_cache):
        """An engine exposing several hooks is torn down exactly ONCE —
        the first match in the documented preference order."""
        ec = clean_engine_cache
        both = _FakeEngine(
            hooks=("close", "quit", "stop", "shutdown", "_cleanup_process", "_cleanup")
        )
        ec._engines["multi"] = both
        ec.clear_cache()
        assert both.calls == ["close"]

    def test_all_engines_raising_still_clears(self, clean_engine_cache):
        ec = clean_engine_cache
        for i in range(3):
            ec._engines[f"bad:{i}"] = _FakeEngine(hooks=("close",), raise_on="close")
        ec.clear_cache()
        assert ec._engines == {}

    def test_empty_cache_is_a_noop(self, clean_engine_cache):
        ec = clean_engine_cache
        ec.clear_cache()  # no engines — must not raise
        assert ec._engines == {}
        assert ec.cached_engine_count() == 0

    def test_quit_hook_preferred_when_no_close(self, clean_engine_cache):
        ec = clean_engine_cache
        quitter = _FakeEngine(hooks=("quit", "_cleanup"))
        ec._engines["x"] = quitter
        ec.clear_cache()
        assert quitter.calls == ["quit"]


class TestWc12AppShutdownWiring:
    """ui_qt/app.py must release the TTS engines in the shutdown path."""

    def _close_event(self) -> str:
        return _method(_APP, "ElixirWindow", "closeEvent")

    def test_close_event_calls_clear_cache(self):
        src = self._close_event()
        assert "from core.tts.engine_cache import clear_cache" in src
        assert "clear_cache()" in src

    def test_clear_cache_after_worker_retire_before_final_quit(self):
        """Ordering pin: AFTER the worker park/join, BEFORE the final
        super().closeEvent(event) — engines are released once the writers
        are parked and the user data (settings + geometry) is saved."""
        src = _strip_comments(self._close_event())
        retire = src.find("self._retire_conversion_workers()")
        save = src.find("self.controller.settings.save()")
        release = src.find("clear_cache()")
        final = src.find("super().closeEvent(event)")
        assert -1 not in (retire, save, release, final)
        assert retire < save < release < final

    def test_clear_cache_call_is_never_raise(self):
        """The release is wrapped in try/except Exception: pass — a stuck
        engine must never block shutdown."""
        src = _strip_comments(self._close_event())
        release = src.find("clear_cache()")
        assert release != -1
        window = src[max(0, release - 400) : release + 200]
        assert "try:" in window
        assert "except Exception:" in window
        assert "pass" in window.split("clear_cache()", 1)[1]

    def test_import_is_local_not_module_level(self):
        """ui_qt/app.py must NOT import engine_cache at module level — the
        rig's UI tests run without PySide6, and the import stays lazy in
        the shutdown path (matches the brief's wiring)."""
        assert "engine_cache" not in _strip_comments(_src(_APP).split("class ElixirWindow", 1)[0])


class TestWc12EngineCacheSourcePins:
    def test_teardown_hook_preference_order_pinned(self):
        body = _strip_comments(_function(_ENGINE_CACHE, "clear_cache"))
        # public names first (foreign/test engines), then the package's
        # private per-engine teardown contract — order matters (first found
        # wins), so pin the tuple verbatim modulo line wrapping.
        flat = " ".join(body.split())
        assert '("close", "quit", "stop", "shutdown", "_cleanup_process", "_cleanup")' in flat

    def test_iterates_a_snapshot_of_the_dict(self):
        """list(_engines.items()) — hooks may mutate the cache; iteration
        must not be disturbed."""
        body = _strip_comments(_function(_ENGINE_CACHE, "clear_cache"))
        assert "for key, engine in list(_engines.items()):" in body

    def test_per_engine_never_raise_guard(self):
        body = _strip_comments(_function(_ENGINE_CACHE, "clear_cache"))
        assert "except Exception" in body
        # the dict clear happens AFTER the teardown loop, unconditionally
        # (rindex: the docstring also mentions ``_engines.clear()`` — pin
        # the LAST, i.e. the executed, occurrence)
        assert (
            body.index("for key, engine in list(_engines.items()):")
            < body.index("except Exception")
            < body.rindex("_engines.clear()")
        )

    def test_getters_unchanged(self):
        """The cache getters keep their get-or-create shape — only the
        dead clear_cache() was fixed."""
        src = _strip_comments(_src(_ENGINE_CACHE))
        assert "def get_neutts_engine(" in src
        assert "def get_qwen_tts_engine(" in src
        assert "def get_sherpa_engine(" in src
        assert "def get_vibevoice_engine(" in src
        assert "def get_kokoro_engine(" in src
        assert "def get_piper_engine(" in src
        assert "def cached_engine_count()" in src

    def test_docstring_documents_the_w_c12_contract(self):
        body = _function(_ENGINE_CACHE, "clear_cache")
        assert "V18.20.4.12 (W-c12)" in body
        assert "GRACEFULLY torn down" in body
        assert "NEVER raise" in body


# ── file hygiene ────────────────────────────────────────────────────────────


class TestFilesParse:
    def test_all_touched_runtime_files_still_parse(self):
        for f in (_SETTINGS, _ENGINE_CACHE, _APP):
            ast.parse(_src(f))
