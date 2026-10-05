"""Phase 2 (Test-Net Deepening) — ``core/llm/model_singletons.py`` push.

Baseline: 65/192 statements missed (66%).

Hermetic strategy:
  - ``Path`` inside the module is swapped for a subclass whose ``home()``
    points at a tmp dir, so the ``~/.elixir/models/...`` lookups never touch
    the real home directory.
  - ``sentence_transformers`` is NOT installed in this sandbox; a fake module
    is injected into ``sys.modules`` (and removed afterwards).
  - ``utils.settings.Settings`` is swapped for a tiny fake (the module imports
    it lazily inside functions).
  - The module-level singletons (``_embed_model``, ``_embed_model_name``,
    ``_FORCE_CPU_EMBEDDER``, ``_spacy_nlp_cache``) are snapshotted and
    restored after every test.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import core.llm.model_singletons as ms  # noqa: E402


class _FakeSettings:
    """Minimal Settings duck-type: ``get(path, default)``."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = data or {}

    def get(self, path: str, default: Any = None):
        return self._data.get(path, default)


class _FakeSentenceTransformer:
    """Fake HF model: encodes to a healthy 64-dim vector, can fail on demand."""

    instances: list[_FakeSentenceTransformer] = []

    def __init__(self, name_or_path: str = "", device: str = "", fail: bool = False) -> None:
        self.name_or_path = name_or_path
        self.device = device
        self.fail = fail
        self.saved_to: list[str] = []
        _FakeSentenceTransformer.instances.append(self)

    def encode(self, texts, convert_to_numpy=True, **kwargs):
        if self.fail:
            raise RuntimeError("CUDA OOM")
        if isinstance(texts, str):
            return np.full(64, 0.25, dtype=np.float32)
        return np.stack([np.full(64, 0.25, dtype=np.float32) for _ in texts])

    def save(self, path: str) -> None:
        self.saved_to.append(path)


def _install_fake_st(monkeypatch: pytest.MonkeyPatch, **ctor_kwargs) -> None:
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = lambda name, device="": _FakeSentenceTransformer(  # type: ignore[attr-defined]
        name, device, **ctor_kwargs
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)


@pytest.fixture(autouse=True)
def _isolated_singletons(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Snapshot/restore module globals + hermetic home + hermetic settings."""
    saved = (
        ms._embed_model,
        ms._embed_model_name,
        ms._FORCE_CPU_EMBEDDER,
        dict(ms._spacy_nlp_cache),
    )
    _FakeSentenceTransformer.instances.clear()

    class _TmpHomePath(Path):
        @classmethod
        def home(cls) -> Path:
            return tmp_path

    monkeypatch.setattr(ms, "Path", _TmpHomePath)
    monkeypatch.setattr(ms, "_FORCE_CPU_EMBEDDER", False)
    # Hermetic net guard: any test that DOESN'T patch safe_ollama_request
    # itself fails loudly instead of dialing localhost:11434.
    import utils.network as _net

    def _no_real_http(*a, **k):  # pragma: no cover - guard, should never run
        raise AssertionError("unexpected real HTTP call in model_singletons test")

    monkeypatch.setattr(_net, "safe_ollama_request", _no_real_http)
    ms._embed_model = None
    ms._embed_model_name = None
    ms._spacy_nlp_cache.clear()
    sys.modules.pop("sentence_transformers", None)
    try:
        yield tmp_path
    finally:
        ms._embed_model, ms._embed_model_name, force_cpu, nlp_cache = saved
        ms._FORCE_CPU_EMBEDDER = force_cpu
        ms._spacy_nlp_cache.clear()
        ms._spacy_nlp_cache.update(nlp_cache)
        sys.modules.pop("sentence_transformers", None)


def _settings(monkeypatch: pytest.MonkeyPatch, data: dict | None = None) -> None:
    monkeypatch.setattr("utils.settings.Settings", lambda: _FakeSettings(data))


# ── Offline env snapshot/restore helpers ────────────────────────────────────


class TestOfflineEnvHelpers:
    def test_snapshot_captures_none_for_unset(self, monkeypatch):
        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
        assert ms._snapshot_offline_env() == {
            "HF_HUB_OFFLINE": None,
            "TRANSFORMERS_OFFLINE": None,
        }

    def test_snapshot_captures_values(self, monkeypatch):
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
        assert ms._snapshot_offline_env() == {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "0",
        }

    def test_restore_removes_unset_keys(self, monkeypatch):
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        ms._restore_offline_env({"HF_HUB_OFFLINE": None})
        assert "HF_HUB_OFFLINE" not in __import__("os").environ

    def test_restore_restores_prior_values(self, monkeypatch):
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        ms._restore_offline_env({"HF_HUB_OFFLINE": "0"})
        assert __import__("os").environ["HF_HUB_OFFLINE"] == "0"


# ── _resolve_embed_device ───────────────────────────────────────────────────


class TestResolveEmbedDevice:
    def test_cpu_preference(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "cpu"})
        assert ms._resolve_embed_device() == "cpu"

    def test_cuda_preference_without_torch_falls_back(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "cuda"})
        sys.modules.pop("torch", None)
        assert ms._resolve_embed_device() == "cpu"

    def test_settings_failure_defaults_to_auto(self, monkeypatch):
        def broken():
            raise RuntimeError("no settings")

        monkeypatch.setattr("utils.settings.Settings", broken)
        # torch missing → auto path → cpu
        sys.modules.pop("torch", None)
        assert ms._resolve_embed_device() == "cpu"

    def test_auto_without_torch_returns_cpu(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        sys.modules.pop("torch", None)
        assert ms._resolve_embed_device() == "cpu"

    def test_auto_force_cpu_flag(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        monkeypatch.setattr(ms, "_FORCE_CPU_EMBEDDER", True)
        assert ms._resolve_embed_device() == "cpu"

    def _fake_torch(self, monkeypatch, available: bool, total_gb: float, alloc_gb: float):
        torch = types.ModuleType("torch")

        class _Props:
            total_memory = total_gb * 1024**3

        torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
            is_available=lambda: available,
            get_device_properties=lambda idx: _Props(),
            memory_allocated=lambda idx: alloc_gb * 1024**3,
        )
        monkeypatch.setitem(sys.modules, "torch", torch)

    def test_auto_with_free_vram_picks_cuda(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        self._fake_torch(monkeypatch, available=True, total_gb=12.0, alloc_gb=2.0)
        assert ms._resolve_embed_device() == "cuda"

    def test_auto_low_vram_stays_cpu(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        self._fake_torch(monkeypatch, available=True, total_gb=12.0, alloc_gb=11.9)
        assert ms._resolve_embed_device() == "cpu"

    def test_auto_cuda_unavailable_returns_cpu(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        self._fake_torch(monkeypatch, available=False, total_gb=0.0, alloc_gb=0.0)
        assert ms._resolve_embed_device() == "cpu"

    def test_auto_torch_probe_exception_returns_cpu(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "auto"})
        torch = types.ModuleType("torch")
        torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
            is_available=lambda: True,
            get_device_properties=lambda idx: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        monkeypatch.setitem(sys.modules, "torch", torch)
        assert ms._resolve_embed_device() == "cpu"

    def test_cuda_preference_with_fake_torch(self, monkeypatch):
        _settings(monkeypatch, {"embedding.device": "cuda"})
        self._fake_torch(monkeypatch, available=True, total_gb=8.0, alloc_gb=0.0)
        assert ms._resolve_embed_device() == "cuda"


# ── get_embed_model — Ollama backend ────────────────────────────────────────


class TestGetEmbedModelOllama:
    def test_ollama_backend_selected_and_smoke_tested(self, monkeypatch):
        _settings(monkeypatch, {"embedding.model": "qwen3-embed"})
        import utils.network as net

        def fake_request(method, url, timeout=60, **kwargs):
            class _R:
                def json(self):
                    return {"embeddings": [[0.5] * 64]}

            return _R()

        monkeypatch.setattr(net, "safe_ollama_request", fake_request)
        model = ms.get_embed_model()
        from core.llm.embedder_backend import OllamaEmbedBackend

        assert isinstance(model, OllamaEmbedBackend)
        assert model.model_name == "qwen3-embed"
        assert model.healthy is True
        # Singleton: second call returns the same instance.
        assert ms.get_embed_model() is model

    def test_ollama_backend_base_url_from_settings(self, monkeypatch):
        _settings(
            monkeypatch,
            {"embedding.model": "qwen3-embed", "llm.ollama_url": "http://localhost:11500"},
        )
        import utils.network as net

        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        model = ms.get_embed_model()
        assert model.base_url == "http://localhost:11500"

    def test_default_model_name_resolves_from_settings(self, monkeypatch):
        _settings(monkeypatch, {})  # embedding.model missing → default
        import utils.network as net

        seen: list[dict] = []

        def fake_request(method, url, timeout=60, **kwargs):
            seen.append(kwargs.get("json"))
            return types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]})

        monkeypatch.setattr(net, "safe_ollama_request", fake_request)
        model = ms.get_embed_model()
        assert model.model_name == "nomic-embed-text"  # the V18.15.1 default

    def test_settings_failure_uses_default_model(self, monkeypatch):
        def broken():
            raise RuntimeError("boom")

        monkeypatch.setattr("utils.settings.Settings", broken)
        import utils.network as net

        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        model = ms.get_embed_model()
        assert model.model_name == "nomic-embed-text"


# ── get_embed_model — HF/sentence-transformers backend ─────────────────────


class TestGetEmbedModelHF:
    def test_disk_load_success_wraps_and_smoke_tests(self, monkeypatch, tmp_path: Path):
        _install_fake_st(monkeypatch)
        _settings(monkeypatch, {"embedding.device": "cpu"})
        model_dir = tmp_path / ".elixir" / "models" / "BAAI--all-MiniLM-L6-v2"
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        import os

        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

        model = ms.get_embed_model("BAAI/all-MiniLM-L6-v2")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)
        assert model.healthy is True
        # V18.20.4.12 (W-c17): the offline flags are SCOPED to the load —
        # restored afterwards, not leaked process-wide.
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_disk_load_failure_falls_through_to_download(self, monkeypatch, tmp_path: Path):
        _install_fake_st(monkeypatch)
        _settings(monkeypatch, {"embedding.device": "cpu"})
        model_dir = tmp_path / ".elixir" / "models" / "org--broken-model"
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        # Make ONLY the from-disk constructor fail (path-based) — the
        # download path (name-based) must still succeed.
        real_st = sys.modules["sentence_transformers"].SentenceTransformer

        def ctor(name, device=""):
            # Only the FROM-DISK load (a filesystem path) fails; the fresh
            # download (the bare repo id) succeeds.
            if "models" in str(name):
                raise ValueError("corrupt local copy")
            return real_st(name, device=device)

        sys.modules["sentence_transformers"].SentenceTransformer = ctor
        model = ms.get_embed_model("org/broken-model")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)

    def test_download_success_saves_and_wraps(self, monkeypatch, tmp_path: Path):
        _install_fake_st(monkeypatch)
        _settings(monkeypatch, {"embedding.device": "cpu"})
        model = ms.get_embed_model("org/fresh-model")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)
        assert model.healthy is True
        # The model was saved to the persistent dir.
        assert (tmp_path / ".elixir" / "models" / "org--fresh-model").exists()
        # Singleton caching by name.
        assert ms.get_embed_model("org/fresh-model") is model

    def test_download_retry_then_success(self, monkeypatch, tmp_path: Path):
        """First download attempt raises → retry warning → second succeeds."""
        _settings(monkeypatch, {"embedding.device": "cpu"})
        attempts = {"n": 0}
        fake_module = types.ModuleType("sentence_transformers")

        def ctor(name, device=""):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ConnectionError("hub unreachable")
            return _FakeSentenceTransformer(name, device)

        fake_module.SentenceTransformer = ctor  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
        model = ms.get_embed_model("org/retry-model")
        assert attempts["n"] == 2
        assert model is not None

    def test_download_failure_both_attempts_returns_none(self, monkeypatch, tmp_path: Path):
        _settings(monkeypatch, {"embedding.device": "cpu"})
        fake_module = types.ModuleType("sentence_transformers")

        def ctor(name, device=""):
            raise ConnectionError("hub unreachable")

        fake_module.SentenceTransformer = ctor  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
        assert ms.get_embed_model("org/doomed-model") is None

    def test_download_timeout_both_attempts_returns_none(self, monkeypatch, tmp_path: Path):
        """Deterministic TimeoutError injection via a fake executor."""
        import concurrent.futures as cf

        _settings(monkeypatch, {"embedding.device": "cpu"})
        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = lambda name, device="": _FakeSentenceTransformer(  # type: ignore[attr-defined]
            name, device
        )
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

        class _FakeFuture:
            def result(self, timeout=None):
                raise cf.TimeoutError()

        class _FakeExecutor:
            def __init__(self, max_workers=1):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def submit(self, fn, *a, **k):
                return _FakeFuture()

        monkeypatch.setattr(cf, "ThreadPoolExecutor", _FakeExecutor)
        assert ms.get_embed_model("org/slow-model") is None

    def test_import_error_returns_none(self, monkeypatch, tmp_path: Path):
        # No sentence_transformers in sys.modules and none installed.
        sys.modules.pop("sentence_transformers", None)
        assert ms.get_embed_model("org/any-hf-model") is None

    def test_outer_exception_returns_none(self, monkeypatch, tmp_path: Path):
        _install_fake_st(monkeypatch)

        def broken_resolve():
            raise RuntimeError("device probe exploded")

        monkeypatch.setattr(ms, "_resolve_embed_device", broken_resolve)
        assert ms.get_embed_model("org/any-model") is None

    def test_disk_load_smoke_test_failure_warns(self, monkeypatch, tmp_path: Path):
        """A from-disk model that loads but emits zero vectors is wrapped
        with healthy=False (V18.2.44) — with a loud WARNING."""
        fake_module = types.ModuleType("sentence_transformers")

        class _Degenerate(_FakeSentenceTransformer):
            def encode(self, texts, convert_to_numpy=True, **kwargs):
                return (
                    np.zeros(64, dtype=np.float32)
                    if isinstance(texts, str)
                    else np.zeros((len(texts), 64), dtype=np.float32)
                )

        fake_module.SentenceTransformer = lambda name, device="": _Degenerate(name, device)  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
        _settings(monkeypatch, {"embedding.device": "cpu"})
        model_dir = tmp_path / ".elixir" / "models" / "org--degenerate"
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        model = ms.get_embed_model("org/degenerate")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)
        assert model.healthy is False

    def test_download_smoke_test_failure_warns(self, monkeypatch, tmp_path: Path):
        """Same V18.2.44 protection for the freshly-downloaded path."""
        fake_module = types.ModuleType("sentence_transformers")

        class _Degenerate(_FakeSentenceTransformer):
            def encode(self, texts, convert_to_numpy=True, **kwargs):
                return (
                    np.zeros(64, dtype=np.float32)
                    if isinstance(texts, str)
                    else np.zeros((len(texts), 64), dtype=np.float32)
                )

        fake_module.SentenceTransformer = lambda name, device="": _Degenerate(name, device)  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
        _settings(monkeypatch, {"embedding.device": "cpu"})

        model = ms.get_embed_model("org/degenerate-dl")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)
        assert model.healthy is False

    def test_ollama_backend_check_exception_falls_to_hf(self, monkeypatch, tmp_path: Path):
        """If the embedder_backend import/probe itself blows up, the getter
        falls through to the sentence-transformers path."""
        _install_fake_st(monkeypatch)
        _settings(monkeypatch, {"embedding.device": "cpu"})

        def broken_is_ollama(name):
            raise ImportError("embedder_backend exploded")

        monkeypatch.setattr("core.llm.embedder_backend.is_ollama_embed_model", broken_is_ollama)
        model = ms.get_embed_model("org/fallback-model")
        from core.llm.embedder_backend import SentenceTransformerBackend

        assert isinstance(model, SentenceTransformerBackend)

    def test_save_failure_is_nonfatal(self, monkeypatch, tmp_path: Path):
        _install_fake_st(monkeypatch)
        _settings(monkeypatch, {"embedding.device": "cpu"})

        class _NoSave(_FakeSentenceTransformer):
            def save(self, path):
                raise OSError("disk full")

        def ctor(name, device=""):
            return _NoSave(name, device)

        sys.modules["sentence_transformers"].SentenceTransformer = ctor
        model = ms.get_embed_model("org/nosave-model")
        assert model is not None  # save failure doesn't kill the load


# ── is_embedder_healthy ─────────────────────────────────────────────────────


class TestIsEmbedderHealthy:
    def test_lazy_load_and_healthy(self, monkeypatch):
        import utils.network as net

        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        _settings(monkeypatch, {"embedding.model": "qwen3-embed"})
        assert ms.is_embedder_healthy() is True

    def test_unhealthy_backend_returns_false(self, monkeypatch):
        import utils.network as net

        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.0] * 64]}),
        )
        _settings(monkeypatch, {"embedding.model": "qwen3-embed"})
        assert ms.is_embedder_healthy() is False

    def test_none_model_returns_false(self, monkeypatch, tmp_path: Path):
        sys.modules.pop("sentence_transformers", None)
        _settings(monkeypatch, {"embedding.model": "hf/model-nevers"})
        assert ms.is_embedder_healthy() is False

    def test_low_bit_quant_model_forces_cpu_flag(self, monkeypatch):
        """IQ2_XXS summarisation model → _FORCE_CPU_EMBEDDER set before load."""
        import utils.network as net

        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        _settings(
            monkeypatch,
            {
                "embedding.model": "qwen3-embed",
                "summarisation.model": "Qwen3.8-27B-UD-IQ2_XXS-Instruct-Vision:latest",
            },
        )
        assert ms.is_embedder_healthy() is True
        assert ms._FORCE_CPU_EMBEDDER is True

    def test_already_loaded_short_circuits(self, monkeypatch):
        marker = types.SimpleNamespace(healthy=True)
        ms._embed_model = marker
        assert ms.is_embedder_healthy() is True

    def test_iq2_check_exception_is_swallowed(self, monkeypatch):
        """A broken Settings during the IQ2_XXS check must not crash the
        health probe — it falls back to a plain lazy load.

        V0.6.8 (audit B11, contract evolution): the broken Settings now
        raises OSError — the realistic settings-read failure family the
        narrowed except still absorbs (with a WARNING). The old
        RuntimeError variant moved to
        test_iq2_check_unexpected_exception_surfaces."""
        import utils.network as net

        def broken_settings():
            raise OSError("settings file unreadable")

        monkeypatch.setattr("utils.settings.Settings", broken_settings)
        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        assert ms.is_embedder_healthy() is True  # default model loads fine

    def test_iq2_check_unexpected_exception_surfaces(self, monkeypatch):
        """V0.6.8 (audit B11): the low-bit-quant check's swallow is
        NARROWED — an exception outside (ImportError/OSError/ValueError)
        now propagates out of the probe instead of being silently
        absorbed (the CPU force-off silently not happening). The probe's
        callers guard it (bullet_pipeline's B10 guard fails safe)."""
        import utils.network as net

        def bug_settings():
            raise RuntimeError("a code bug, not a settings failure")

        monkeypatch.setattr("utils.settings.Settings", bug_settings)
        monkeypatch.setattr(
            net,
            "safe_ollama_request",
            lambda *a, **k: types.SimpleNamespace(json=lambda: {"embeddings": [[0.5] * 64]}),
        )
        with pytest.raises(RuntimeError, match="a code bug"):
            ms.is_embedder_healthy()


# ── get_spacy_nlp ───────────────────────────────────────────────────────────


class _FakeSpacy:
    def __init__(self) -> None:
        self.loaded: list[tuple[str, list | None]] = []

    def load(self, model_name: str, disable=None):
        if model_name == "missing_model":
            raise OSError(f"[E050] Can't find model '{model_name}'")
        self.loaded.append((model_name, disable))
        return types.SimpleNamespace(model=model_name)


@pytest.fixture
def fake_spacy(monkeypatch: pytest.MonkeyPatch) -> _FakeSpacy:
    spacy = _FakeSpacy()
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    return spacy


class TestGetSpacyNlp:
    def test_load_and_cache(self, fake_spacy):
        nlp = ms.get_spacy_nlp("en_core_web_sm")
        assert nlp.model == "en_core_web_sm"
        assert ms.get_spacy_nlp("en_core_web_sm") is nlp  # cached
        assert fake_spacy.loaded == [("en_core_web_sm", None)]

    def test_load_with_disable(self, fake_spacy):
        nlp = ms.get_spacy_nlp("en_core_web_sm", disable=["parser", "tagger"])
        assert fake_spacy.loaded == [("en_core_web_sm", ["parser", "tagger"])]
        assert nlp is not None

    def test_missing_model_returns_none(self, fake_spacy):
        assert ms.get_spacy_nlp("missing_model") is None
        assert "missing_model" not in ms._spacy_nlp_cache

    def test_spacy_import_error_returns_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "spacy", None)  # import spacy → ImportError
        assert ms.get_spacy_nlp("en_core_web_sm") is None


# ── reset_singletons ────────────────────────────────────────────────────────


class TestResetSingletons:
    def test_reset_clears_everything(self, fake_spacy):
        ms.get_spacy_nlp("en_core_web_sm")
        ms._embed_model = types.SimpleNamespace()
        ms._embed_model_name = "x"
        ms.reset_singletons()
        assert ms._embed_model is None
        assert ms._embed_model_name is None
        assert ms._spacy_nlp_cache == {}
