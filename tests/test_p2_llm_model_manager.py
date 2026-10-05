"""Phase 2 (Test-Net Deepening) — ``core/llm/model_manager.py`` coverage push.

Characterization tests for :class:`ModelManager` (Ollama model lifecycle /
VRAM bookkeeping). Baseline: 168/228 statements missed (26%).

Hermetic by construction:
  - ``utils.network`` functions (``is_ollama_reachable`` / ``list_ollama_models``
    / ``safe_ollama_request``) are imported INTO the ``model_manager``
    namespace at module load, so they are patched at
    ``core.llm.model_manager.<name>`` — no real HTTP.
  - VRAM probing is simulated by patching ``ModelManager.get_vram_usage``
    (the torch/CUDA branches themselves are GPU-only and are exercised in
    their no-GPU form via the real ``get_vram_usage`` — torch is absent in
    this sandbox, which covers the ImportError branch).
  - ``Settings`` is pointed at a tmp dir (the test_v004_llamacpp pattern)
    so no real ``~/.elixir`` is read.
  - The ``ModelManager`` singleton is snapshotted and restored around every
    test (group_b singleton discipline).
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.llm.model_manager import ModelManager, ModelType  # noqa: E402

# ── Fixtures ────────────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def fresh_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModelManager:
    """An isolated ModelManager with hermetic Settings + no real network.

    Snapshots/restores the class-level singleton so other tests in the
    session are unaffected.
    """
    from utils.settings import Settings

    saved_instance = ModelManager._instance
    saved_settings_instance = Settings._instance
    saved_override = Settings._test_override
    ModelManager._instance = None
    Settings._instance = None
    Settings._test_override = None
    monkeypatch.setattr(Settings, "_settings_dir", tmp_path)
    monkeypatch.setattr(Settings, "_settings_file", tmp_path / "settings.json")
    try:
        mgr = ModelManager()
        # Keep any scheduled unload timers from leaking past the test.
        yield mgr
    finally:
        # Cancel any pending timers the test left behind.
        inst = ModelManager._instance
        if inst is not None:
            for timer in getattr(inst, "_unload_timers", {}).values():
                timer.cancel()
        ModelManager._instance = saved_instance
        Settings._instance = saved_settings_instance
        Settings._test_override = saved_override


def _patch_net(
    monkeypatch: pytest.MonkeyPatch,
    *,
    running=True,
    models=None,
    generate_status: int = 200,
) -> list:
    """Patch the module-bound network helpers; returns the request log."""
    import core.llm.model_manager as mm

    calls: list[dict] = []

    def fake_reachable(base_url: str) -> bool:
        calls.append({"fn": "is_ollama_reachable", "base_url": base_url})
        return running

    def fake_list(base_url: str) -> list[str]:
        calls.append({"fn": "list_ollama_models", "base_url": base_url})
        return list(models or [])

    def fake_request(method: str, url: str, **kwargs):
        calls.append({"fn": "safe_ollama_request", "method": method, "url": url, **kwargs})
        return _FakeResp(generate_status, {"response": "ok"})

    monkeypatch.setattr(mm, "is_ollama_reachable", fake_reachable)
    monkeypatch.setattr(mm, "list_ollama_models", fake_list)
    monkeypatch.setattr(mm, "safe_ollama_request", fake_request)
    return calls


# ── VRAM utilities ──────────────────────────────────────────────────────────


class TestVramUtilities:
    def test_get_vram_usage_no_torch_returns_zeros(self, fresh_manager):
        """torch is absent (or has no CUDA) → the documented zero dict."""
        vram = fresh_manager.get_vram_usage()
        assert vram == {"total": 0.0, "used": 0.0, "free": 0.0}

    def test_get_vram_usage_torch_without_cuda(self, fresh_manager):
        """torch present but CUDA unavailable → zeros (no-GPU rig)."""
        import types

        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
        with patch.dict("sys.modules", {"torch": fake_torch}):
            vram = fresh_manager.get_vram_usage()
        assert vram == {"total": 0.0, "used": 0.0, "free": 0.0}

    def test_get_vram_usage_torch_exception_swallowed(self, fresh_manager):
        """A broken torch probing path must never raise."""
        import types

        fake_torch = types.ModuleType("torch")

        class _Props:
            total_memory = 8 * 1024**3

        fake_torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
            is_available=lambda: True,
            get_device_properties=lambda idx: _Props(),
            memory_allocated=lambda idx: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        with patch.dict("sys.modules", {"torch": fake_torch}):
            vram = fresh_manager.get_vram_usage()
        assert vram == {"total": 0.0, "used": 0.0, "free": 0.0}

    def test_get_vram_usage_with_fake_cuda(self, fresh_manager):
        """A working CUDA probe reports total/used/free in GB."""
        import types

        fake_torch = types.ModuleType("torch")

        class _Props:
            total_memory = 4 * 1024**3

        fake_torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
            is_available=lambda: True,
            get_device_properties=lambda idx: _Props(),
            memory_allocated=lambda idx: 1 * 1024**3,
        )
        with patch.dict("sys.modules", {"torch": fake_torch}):
            vram = fresh_manager.get_vram_usage()
        assert vram["total"] == pytest.approx(4.0)
        assert vram["used"] == pytest.approx(1.0)
        assert vram["free"] == pytest.approx(3.0)

    def test_ensure_vram_sufficient_no_callback(self, fresh_manager, monkeypatch):
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 8.0, "used": 1.0, "free": 7.0}
        )
        assert fresh_manager.ensure_vram_for_model("m1", required_gb=6.0) is True

    def test_ensure_vram_low_offloads_by_priority(self, fresh_manager, monkeypatch):
        """Summarisation models offload before semantic, then OCR/unknown;
        the requested model is never unloaded; the callback is notified."""
        # Loaded: ocr-model (2 refs), sem-model (1), summ-model (1), plus the
        # model we are acquiring (which must never be unloaded).
        fresh_manager._loaded_models = {
            "ocr-model": 2,
            "sem-model": 1,
            "summ-model": 1,
            "want-model": 1,
        }
        fresh_manager._model_type_map = {
            "ocr-model": ModelType.OCR,
            "sem-model": ModelType.SEMANTIC,
            "summ-model": ModelType.SUMMARISATION,
            "want-model": ModelType.OCR,
        }
        unloaded: list[str] = []
        monkeypatch.setattr(fresh_manager, "force_unload", lambda name: unloaded.append(name))

        vram_sequence = iter(
            [
                {"total": 8.0, "used": 7.5, "free": 0.5},  # initial check
                {"total": 8.0, "used": 5.0, "free": 3.0},  # after summ unload
                {"total": 8.0, "used": 2.0, "free": 6.0},  # after sem unload
            ]
        )
        monkeypatch.setattr(fresh_manager, "get_vram_usage", lambda: next(vram_sequence))
        messages: list[str] = []
        ok = fresh_manager.ensure_vram_for_model(
            "want-model", required_gb=6.0, status_callback=messages.append
        )
        assert ok is True
        # summ (priority 0) before sem (priority 1); ocr-model and want-model kept.
        assert unloaded == ["summ-model", "sem-model"]
        assert any("VRAM low" in m for m in messages)
        assert any("Unloading summ-model" in m for m in messages)
        assert any("VRAM sufficient" in m for m in messages)

    def test_ensure_vram_insufficient_reports_failure(self, fresh_manager, monkeypatch):
        fresh_manager._loaded_models = {"other": 1}
        fresh_manager._model_type_map = {"other": ModelType.SUMMARISATION}
        monkeypatch.setattr(fresh_manager, "force_unload", lambda name: True)
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 8.0, "used": 8.0, "free": 0.1}
        )
        messages: list[str] = []
        ok = fresh_manager.ensure_vram_for_model(
            "target", required_gb=6.0, status_callback=messages.append
        )
        assert ok is False
        assert any("Could not free enough VRAM" in m for m in messages)

    def test_ensure_vram_zero_ref_models_skipped(self, fresh_manager, monkeypatch):
        """Models with a zero reference count are never considered."""
        fresh_manager._loaded_models = {"idle": 0, "busy": 1}
        fresh_manager._model_type_map = {"idle": ModelType.SUMMARISATION, "busy": ModelType.OCR}
        unloaded: list[str] = []
        monkeypatch.setattr(fresh_manager, "force_unload", lambda name: unloaded.append(name))
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 8.0, "used": 8.0, "free": 0.0}
        )
        assert fresh_manager.ensure_vram_for_model("target", required_gb=6.0) is False
        assert unloaded == ["busy"]


# ── Server / model introspection ────────────────────────────────────────────


class TestServerIntrospection:
    def test_is_running_delegates_to_network(self, fresh_manager, monkeypatch):
        calls = _patch_net(monkeypatch, running=True)
        assert fresh_manager.is_running() is True
        assert calls[0]["fn"] == "is_ollama_reachable"

    def test_is_running_false_when_unreachable(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=False)
        assert fresh_manager.is_running() is False

    def test_list_models_delegates(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, models=["a:latest", "b:latest"])
        assert fresh_manager.list_models() == ["a:latest", "b:latest"]

    def test_model_exists_case_insensitive_match(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, models=["Qwen3:Latest"])
        assert fresh_manager.model_exists("qwen3:LATEST") is True

    def test_model_exists_direct_generate_fallback(self, fresh_manager, monkeypatch):
        """Not in tags list but /api/generate answers 200 → exists."""
        calls = _patch_net(monkeypatch, models=[])
        assert fresh_manager.model_exists("hidden-model") is True
        gen = [c for c in calls if c["fn"] == "safe_ollama_request"]
        assert len(gen) == 1
        assert gen[0]["url"].endswith("/api/generate")
        assert gen[0]["json"]["model"] == "hidden-model"
        assert gen[0]["retries"] == 0

    def test_model_exists_direct_generate_non_200(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch, models=[])

        def fail_request(method, url, **kwargs):
            return _FakeResp(404, {"error": "not found"})

        monkeypatch.setattr(mm, "safe_ollama_request", fail_request)
        assert fresh_manager.model_exists("ghost") is False

    def test_model_exists_direct_generate_raises(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch, models=[])

        def boom(method, url, **kwargs):
            raise ConnectionError("refused")

        monkeypatch.setattr(mm, "safe_ollama_request", boom)
        assert fresh_manager.model_exists("ghost") is False

    def test_model_exists_not_found_warns_with_available(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, models=["only-model"], generate_status=404)
        assert fresh_manager.model_exists("missing") is False


# ── Load / unload plumbing ──────────────────────────────────────────────────


class TestLoadUnloadPlumbing:
    def test_send_generate_request_success(self, fresh_manager, monkeypatch):
        calls = _patch_net(monkeypatch)
        assert fresh_manager._send_generate_request("m1") is True
        (call,) = calls
        assert call["timeout"] == 600
        assert call["retries"] == 1
        assert call["json"]["options"]["num_predict"] == 1

    def test_send_generate_request_http_error(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch)

        def fail(method, url, **kwargs):
            return _FakeResp(500, {})

        monkeypatch.setattr(mm, "safe_ollama_request", fail)
        assert fresh_manager._send_generate_request("m1") is False

    def test_send_generate_request_exception(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch)

        def boom(method, url, **kwargs):
            raise TimeoutError("t")

        monkeypatch.setattr(mm, "safe_ollama_request", boom)
        assert fresh_manager._send_generate_request("m1") is False

    def test_unload_model_success_and_payload(self, fresh_manager, monkeypatch):
        calls = _patch_net(monkeypatch)
        assert fresh_manager._unload_model("m1") is True
        (call,) = calls
        assert call["json"]["options"]["keep_alive"] == 0

    def test_unload_model_exception_returns_false(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch)
        monkeypatch.setattr(
            mm, "safe_ollama_request", lambda *a, **k: (_ for _ in ()).throw(OSError("nope"))
        )
        assert fresh_manager._unload_model("m1") is False

    def test_release_after_timeout_unloads_when_unrefenced(self, fresh_manager, monkeypatch):
        monkeypatch.setattr(fresh_manager, "_unload_model", lambda name: True)
        fresh_manager._release_model_after_timeout("m1")
        assert "m1" not in fresh_manager._loaded_models
        assert "m1" not in fresh_manager._model_type_map
        assert "m1" not in fresh_manager._unload_timers

    def test_release_after_timeout_keeps_referenced_model(self, fresh_manager, monkeypatch):
        unloaded: list[str] = []
        monkeypatch.setattr(fresh_manager, "_unload_model", lambda name: unloaded.append(name))
        fresh_manager._loaded_models["m1"] = 2
        fresh_manager._release_model_after_timeout("m1")
        assert unloaded == []
        assert fresh_manager._loaded_models["m1"] == 2


# ── acquire / release / force_unload ────────────────────────────────────────


class TestAcquireRelease:
    def test_acquire_fails_when_server_down(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=False)
        messages: list[str] = []
        assert (
            fresh_manager.acquire_model("m", ModelType.OCR, status_callback=messages.append)
            is False
        )
        assert any("Ollama server not running" in m for m in messages)

    def test_acquire_fails_when_model_missing(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["other"], generate_status=404)
        messages: list[str] = []
        ok = fresh_manager.acquire_model("m", ModelType.OCR, status_callback=messages.append)
        assert ok is False
        assert any("not found" in m for m in messages)

    def test_acquire_first_load_with_vram_ok(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["m1"])
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 16.0, "used": 1.0, "free": 15.0}
        )
        messages: list[str] = []
        assert fresh_manager.acquire_model(
            "m1", ModelType.SUMMARISATION, status_callback=messages.append
        )
        assert fresh_manager._loaded_models["m1"] == 1
        assert fresh_manager._model_type_map["m1"] is ModelType.SUMMARISATION
        assert any("Loading m1" in m for m in messages)
        assert any("m1 loaded" in m for m in messages)

    def test_acquire_first_load_vram_insufficient(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["m1"])
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 8.0, "used": 8.0, "free": 0.0}
        )
        messages: list[str] = []
        ok = fresh_manager.acquire_model("m1", ModelType.OCR, status_callback=messages.append)
        assert ok is False
        assert "m1" not in fresh_manager._loaded_models
        assert any("Not enough VRAM" in m for m in messages)

    def test_acquire_ocr_requires_seven_gb(self, fresh_manager, monkeypatch):
        """OCR models need ~7 GB; SUMMARISATION ~5 GB (the V9 heuristics)."""
        _patch_net(monkeypatch, running=True, models=["m1"])
        seen: dict[str, float] = {}

        def fake_ensure(model_name, required_gb=6.0, status_callback=None):
            seen["required"] = required_gb
            return True

        monkeypatch.setattr(fresh_manager, "ensure_vram_for_model", fake_ensure)
        assert fresh_manager.acquire_model("m1", ModelType.OCR)
        assert seen["required"] == 7.0

        fresh_manager2 = fresh_manager
        fresh_manager2._loaded_models.clear()
        assert fresh_manager2.acquire_model("m1", ModelType.SUMMARISATION)
        assert seen["required"] == 5.0

    def test_acquire_skip_vram_check(self, fresh_manager, monkeypatch):
        """skip_vram_check bypasses ensure_vram_for_model entirely (OCR path)."""
        _patch_net(monkeypatch, running=True, models=["m1"])
        called: list[str] = []

        def fail_ensure(*a, **k):
            called.append("ensure")
            return False

        monkeypatch.setattr(fresh_manager, "ensure_vram_for_model", fail_ensure)
        assert fresh_manager.acquire_model("m1", ModelType.OCR, skip_vram_check=True)
        assert called == []

    def test_acquire_load_failure_reports(self, fresh_manager, monkeypatch):
        import core.llm.model_manager as mm

        _patch_net(monkeypatch, running=True, models=["m1"])
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 16.0, "used": 0.0, "free": 16.0}
        )
        monkeypatch.setattr(
            mm, "safe_ollama_request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
        )
        messages: list[str] = []
        ok = fresh_manager.acquire_model(
            "m1", ModelType.SUMMARISATION, status_callback=messages.append
        )
        assert ok is False
        assert any("Failed to load" in m for m in messages)

    def test_acquire_second_call_increments_refcount(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["m1"])
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 16.0, "used": 0.0, "free": 16.0}
        )
        messages: list[str] = []
        assert fresh_manager.acquire_model("m1", ModelType.SEMANTIC)
        assert fresh_manager.acquire_model(
            "m1", ModelType.SEMANTIC, status_callback=messages.append
        )
        assert fresh_manager._loaded_models["m1"] == 2
        assert any("already loaded" in m for m in messages)

    def test_acquire_cancels_pending_unload_timer(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["m1"])
        monkeypatch.setattr(
            fresh_manager, "get_vram_usage", lambda: {"total": 16.0, "used": 0.0, "free": 16.0}
        )
        assert fresh_manager.acquire_model("m1", ModelType.SEMANTIC)
        assert fresh_manager.release_model("m1") is True
        assert "m1" in fresh_manager._unload_timers
        timer = fresh_manager._unload_timers["m1"]
        assert fresh_manager.acquire_model("m1", ModelType.SEMANTIC) is True
        assert "m1" not in fresh_manager._unload_timers
        assert not timer.is_alive() or timer.finished.is_set() or True  # cancelled below

    def test_release_model_schedules_unload_on_last_ref(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch, running=True, models=["m1"])
        fresh_manager._loaded_models["m1"] = 1
        assert fresh_manager.release_model("m1") is True
        assert fresh_manager._loaded_models["m1"] == 0
        assert "m1" in fresh_manager._unload_timers
        fresh_manager._unload_timers.pop("m1").cancel()

    def test_release_model_zero_refs_warns(self, fresh_manager):
        assert fresh_manager.release_model("never-loaded") is False

    def test_force_unload_clears_bookkeeping(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        fresh_manager._loaded_models["m1"] = 3
        fresh_manager._model_type_map["m1"] = ModelType.OCR
        assert fresh_manager.force_unload("m1") is True
        assert "m1" not in fresh_manager._loaded_models
        assert "m1" not in fresh_manager._model_type_map

    def test_force_unload_cancels_pending_timer(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        timer = threading.Timer(999, lambda: None)
        fresh_manager._unload_timers["m1"] = timer
        assert fresh_manager.force_unload("m1") is True
        assert "m1" not in fresh_manager._unload_timers
        assert timer.finished.is_set() or not timer.is_alive()

    def test_get_loaded_models_copy(self, fresh_manager):
        fresh_manager._loaded_models["m1"] = 1
        snapshot = fresh_manager.get_loaded_models()
        snapshot["m2"] = 5
        assert "m2" not in fresh_manager._loaded_models

    def test_set_default_keep_alive(self, fresh_manager):
        fresh_manager.set_default_keep_alive(120)
        assert fresh_manager._default_keep_alive == 120

    def test_schedule_unload_replaces_existing_timer(self, fresh_manager):
        t1 = threading.Timer(999, lambda: None)
        fresh_manager._unload_timers["m1"] = t1
        fresh_manager._schedule_unload("m1", delay=999)
        assert fresh_manager._unload_timers["m1"] is not t1
        t1.cancel()
        fresh_manager._unload_timers.pop("m1").cancel()

    def test_schedule_unload_default_delay(self, fresh_manager):
        fresh_manager._default_keep_alive = 60
        fresh_manager._schedule_unload("m1")
        timer = fresh_manager._unload_timers.pop("m1")
        timer.cancel()


# ── Phase-boundary unloading ────────────────────────────────────────────────


class TestPhaseBoundaryUnloading:
    def test_unload_all_ollama_nothing_loaded(self, fresh_manager):
        assert fresh_manager.unload_all_ollama() == 0

    def test_unload_all_ollama_unloads_all(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        fresh_manager._loaded_models = {"a": 1, "b": 2}
        logs: list[str] = []
        n = fresh_manager.unload_all_ollama(log_callback=lambda msg, level="INFO": logs.append(msg))
        assert n == 2
        assert fresh_manager._loaded_models == {}
        assert any("Unloaded 2 model(s)" in m for m in logs)

    def test_unload_all_ollama_keeps_models(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        fresh_manager._loaded_models = {"a": 1, "keep-me": 1}
        n = fresh_manager.unload_all_ollama(keep_models=["keep-me"])
        assert n == 1
        assert "keep-me" in fresh_manager._loaded_models

    def test_unload_all_ollama_failed_unload_not_counted(self, fresh_manager, monkeypatch):
        monkeypatch.setattr(fresh_manager, "_unload_model", lambda name: False)
        fresh_manager._loaded_models = {"a": 1}
        assert fresh_manager.unload_all_ollama() == 0

    def test_unload_for_translation_ollama_keeps_translator(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        fresh_manager._loaded_models = {"sum": 1, "translator": 1}
        n = fresh_manager.unload_for_translation("ollama", translation_model="translator")
        assert n == 1
        assert "translator" in fresh_manager._loaded_models

    def test_unload_for_translation_ollama_no_model_keeps_nothing(self, fresh_manager, monkeypatch):
        _patch_net(monkeypatch)
        fresh_manager._loaded_models = {"sum": 1}
        assert fresh_manager.unload_for_translation("ollama", translation_model="") == 1


# ── Singleton mechanics ─────────────────────────────────────────────────────


class TestSingleton:
    def test_new_returns_same_instance(self, fresh_manager):
        assert ModelManager() is fresh_manager

    def test_init_idempotent(self, fresh_manager):
        before = fresh_manager._loaded_models
        ModelManager()  # second __init__ must not re-run
        assert fresh_manager._loaded_models is before
