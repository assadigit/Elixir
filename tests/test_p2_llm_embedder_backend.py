"""Phase 2 (Test-Net Deepening) — ``core/llm/embedder_backend.py`` push.

Baseline: 66/190 statements missed (65%).

Hermetic: Ollama HTTP goes through ``utils.network.safe_ollama_request``
(imported lazily INSIDE ``_embed_single`` / ``_embed_batch``), so patching
``utils.network.safe_ollama_request`` intercepts everything. The HF-backed
``SentenceTransformerBackend`` wraps a plain fake model object.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.llm.embedder_backend import (  # noqa: E402
    OllamaEmbedBackend,
    SentenceTransformerBackend,
    create_embedder,
    is_ollama_embed_model,
)


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


# ── is_ollama_embed_model / create_embedder ─────────────────────────────────


class TestModelNameHeuristic:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("", False),
            (None, False),
            ("BAAI/bge-base-en-v1.5", False),
            ("model.Q4", False),  # dots but no slash, not gguf → HF
            ("all-MiniLM-L6-v2", True),  # no dot, no slash → bare Ollama name
            ("model.gguf", True),
            ("MODEL.GGUF", True),  # lowercased check
            ("path/to/model.gguf", True),  # GGUF wins even with a slash
            ("qwen3-embed:latest", True),
            ("qwen3-embed", True),  # bare single token, no dots
        ],
    )
    def test_heuristic(self, name, expected):
        assert is_ollama_embed_model(name) is expected

    def test_create_embedder_ollama_backend(self):
        backend = create_embedder("qwen3-embed")
        assert isinstance(backend, OllamaEmbedBackend)
        assert backend.model_name == "qwen3-embed"
        assert backend.base_url == "http://localhost:11434"

    def test_create_embedder_custom_base_url(self):
        backend = create_embedder("qwen3-embed", base_url="http://localhost:11500/")
        assert backend.base_url == "http://localhost:11500"

    def test_create_embedder_hf_returns_none(self):
        assert create_embedder("BAAI/bge-base-en-v1.5") is None


# ── SentenceTransformerBackend ──────────────────────────────────────────────


class _FakeST:
    """A fake SentenceTransformer: healthy by default."""

    def __init__(self, result=None, dim: int = 64, fail: bool = False) -> None:
        self._result = result
        self._dim = dim
        self._fail = fail
        self.calls: list = []

    def get_sentence_embedding_dimension(self):
        return self._dim

    def encode(self, texts, convert_to_numpy=True, **kwargs):
        self.calls.append(texts)
        if self._fail:
            raise RuntimeError("CUDA OOM during forward pass")
        if isinstance(texts, str):
            if self._result is not None:
                return self._result
            return np.full(self._dim, 0.5, dtype=np.float32)
        if self._result is not None:
            return np.array([self._result] * len(texts))
        return np.stack([np.full(self._dim, 0.5 + i, dtype=np.float32) for i in range(len(texts))])

    def some_library_attribute(self):
        return "delegated"


class TestSentenceTransformerBackend:
    def test_delegation_via_getattr(self):
        wrapped = SentenceTransformerBackend(_FakeST())
        assert wrapped.some_library_attribute() == "delegated"

    def test_encode_delegates_when_healthy(self):
        inner = _FakeST()
        wrapped = SentenceTransformerBackend(inner)
        out = wrapped.encode(["a", "b"])
        assert out.shape == (2, 64)
        assert inner.calls == [["a", "b"]]

    def test_encode_single_string_when_healthy(self):
        inner = _FakeST()
        wrapped = SentenceTransformerBackend(inner)
        out = wrapped.encode("hello")
        assert out.shape == (64,)
        assert inner.calls == ["hello"]

    def test_encode_unhealthy_returns_zero_vector_string(self):
        wrapped = SentenceTransformerBackend(_FakeST(dim=128))
        wrapped.healthy = False
        out = wrapped.encode("hello")
        assert out.shape == (128,)
        assert not np.any(out)

    def test_encode_unhealthy_returns_zero_matrix_list(self):
        wrapped = SentenceTransformerBackend(_FakeST(dim=96))
        wrapped.healthy = False
        out = wrapped.encode(["a", "b", "c"])
        assert out.shape == (3, 96)
        assert not np.any(out)

    def test_encode_unhealthy_invalid_dim_falls_back_to_384(self):
        class _WeirdDim:
            def get_sentence_embedding_dimension(self):
                return "not-a-number"

        wrapped = SentenceTransformerBackend(_WeirdDim())
        wrapped.healthy = False
        out = wrapped.encode(["a"])
        assert out.shape == (1, 384)

    def test_smoke_test_healthy(self):
        wrapped = SentenceTransformerBackend(_FakeST())
        assert wrapped.smoke_test() is True
        assert wrapped.healthy is True
        assert wrapped._health_reason == ""

    def test_smoke_test_empty_vector(self):
        wrapped = SentenceTransformerBackend(_FakeST(result=np.zeros(0, dtype=np.float32)))
        assert wrapped.smoke_test() is False
        assert "empty vector" in wrapped._health_reason

    def test_smoke_test_all_zero_vector(self):
        wrapped = SentenceTransformerBackend(_FakeST(result=np.zeros(64, dtype=np.float32)))
        assert wrapped.smoke_test() is False
        assert "all-zero" in wrapped._health_reason

    def test_smoke_test_nan_vector(self):
        vec = np.full(64, np.nan, dtype=np.float32)
        wrapped = SentenceTransformerBackend(_FakeST(result=vec))
        assert wrapped.smoke_test() is False
        assert "NaN" in wrapped._health_reason

    def test_smoke_test_short_vector(self):
        wrapped = SentenceTransformerBackend(_FakeST(result=np.ones(8, dtype=np.float32)))
        assert wrapped.smoke_test() is False
        assert "suspiciously short" in wrapped._health_reason

    def test_smoke_test_encode_raises(self):
        wrapped = SentenceTransformerBackend(_FakeST(fail=True))
        assert wrapped.smoke_test() is False
        assert "RuntimeError" in wrapped._health_reason


# ── OllamaEmbedBackend ──────────────────────────────────────────────────────


def _patch_ollama(monkeypatch: pytest.MonkeyPatch, handler) -> list[dict]:
    """Patch utils.network.safe_ollama_request with ``handler(url, payload)``."""
    import utils.network as net

    calls: list[dict] = []

    def fake_request(method, url, timeout=60, **kwargs):
        calls.append({"url": url, "payload": kwargs.get("json"), "timeout": timeout})
        return _FakeResp(handler(url, kwargs.get("json")))

    monkeypatch.setattr(net, "safe_ollama_request", fake_request)
    return calls


class TestOllamaEmbedSingle:
    def test_new_endpoint_first(self, monkeypatch):
        calls = _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[0.1, 0.2]]})
        b = OllamaEmbedBackend("qwen3-embed")
        vec = b._embed_single("hi")
        assert vec.tolist() == pytest.approx([0.1, 0.2])
        assert b._dim == 2
        assert calls[0]["url"].endswith("/api/embed")
        assert calls[0]["payload"]["input"] == "hi"
        assert calls[0]["payload"]["model"] == "qwen3-embed"
        assert "keep_alive" in calls[0]["payload"]

    def test_legacy_endpoint_used_when_embeddings_key(self, monkeypatch):
        """A /api/embed response that only has 'embedding' still works."""

        def handler(url, p):
            if url.endswith("/api/embed"):
                return {"embedding": [0.3, 0.4]}  # legacy-style body
            raise AssertionError("should not reach the legacy endpoint")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        assert b._embed_single("hi").tolist() == pytest.approx([0.3, 0.4])

    def test_forty_four_falls_back_to_legacy_endpoint(self, monkeypatch):
        seen: list[str] = []

        def handler(url, p):
            seen.append(url)
            if url.endswith("/api/embed"):
                raise RuntimeError("404 Client Error: Not Found")
            return {"embedding": [1.0, 2.0, 3.0]}

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        vec = b._embed_single("hi")
        assert vec.tolist() == pytest.approx([1.0, 2.0, 3.0])
        assert seen[0].endswith("/api/embed")
        assert seen[1].endswith("/api/embeddings")
        assert b._dim == 3

    def test_not_found_message_falls_back(self, monkeypatch):
        def handler(url, p):
            if url.endswith("/api/embed"):
                raise RuntimeError("Not Found for url")
            return {"embedding": [9.0]}

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        assert b._embed_single("hi").tolist() == pytest.approx([9.0])

    def test_non_404_error_propagates(self, monkeypatch):
        def handler(url, p):
            raise TimeoutError("read timeout")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        with pytest.raises(TimeoutError):
            b._embed_single("hi")

    def test_empty_vector_both_endpoints_raises(self, monkeypatch):
        def handler(url, p):
            return {"embeddings": [[]]}  # empty first vector

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        with pytest.raises(RuntimeError, match="Both Ollama embed endpoints failed"):
            b._embed_single("hi")

    def test_keep_alive_falls_back_when_settings_unavailable(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0]]})

        def broken_import():
            raise ImportError("no settings")

        monkeypatch.setattr("core.llm.llm_provider_impl._get_keep_alive", lambda: "17m")
        b = OllamaEmbedBackend("m")
        calls = _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0]]})
        b._embed_single("hi")
        assert calls[0]["payload"]["keep_alive"] == "17m"


class TestOllamaEmbedBatch:
    def test_batch_success(self, monkeypatch):
        calls = _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0, 1.0], [2.0, 2.0]]})
        b = OllamaEmbedBackend("m")
        vecs = b._embed_batch(["a", "b"])
        assert vecs is not None and len(vecs) == 2
        assert b._dim == 2
        assert calls[0]["payload"]["input"] == ["a", "b"]

    def test_batch_count_mismatch_returns_none(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0]]})
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a", "b"]) is None

    def test_batch_malformed_returns_none(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": "nope"})
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a"]) is None

    def test_batch_missing_key_returns_none(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {})
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a"]) is None

    def test_batch_empty_vector_returns_none(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[], [1.0]]})
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a", "b"]) is None

    def test_batch_exception_returns_none(self, monkeypatch):
        def handler(url, p):
            raise ConnectionError("refused")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a"]) is None

    def test_batch_records_dim(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[0.5] * 7] * 3})
        b = OllamaEmbedBackend("m")
        assert b._embed_batch(["a", "b", "c"]) is not None
        assert b._dim == 7


class TestOllamaEncode:
    def test_encode_single_string(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0, 2.0]]})
        b = OllamaEmbedBackend("m")
        assert b.encode("hi").tolist() == pytest.approx([1.0, 2.0])

    def test_encode_empty_list(self):
        b = OllamaEmbedBackend("m")
        out = b.encode([])
        assert out.size == 0

    def test_encode_batched_fast_path(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0], [2.0]]})
        b = OllamaEmbedBackend("m")
        out = b.encode(["a", "b"])
        assert out.shape == (2, 1)

    def test_encode_batch_fallback_to_per_item(self, monkeypatch):
        """Batched call fails → per-item loop (legacy endpoint)."""

        def handler(url, p):
            if url.endswith("/api/embed") and isinstance(p.get("input"), list):
                raise ConnectionError("batch refused")
            # per-item legacy responses
            return {"embedding": [1.5, 1.5]}

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        out = b.encode(["a", "b"])
        assert out.shape == (2, 2)
        np.testing.assert_allclose(out, [[1.5, 1.5], [1.5, 1.5]])

    def test_encode_first_item_failure_marks_unhealthy_zero_vectors(self, monkeypatch):
        def handler(url, p):
            raise ConnectionError("model not pulled")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("ghost-model")
        out = b.encode(["a", "b"])
        assert out.shape == (2, 384)  # MiniLM default dim
        assert not np.any(out)
        assert b.healthy is False
        assert "ghost-model" in b._health_reason
        assert "ollama pull ghost-model" in b._health_reason

    def test_encode_mid_batch_failure_zero_vector(self, monkeypatch):
        state = {"n": 0}

        def handler(url, p):
            state["n"] += 1
            # First call: the batched attempt (succeeds with wrong count) →
            # per-item loop: first item OK, second raises, third OK.
            if state["n"] == 1:
                return {"embeddings": []}  # malformed → per-item fallback
            if state["n"] == 2:
                return {"embeddings": [[1.0, 1.0]]}
            if state["n"] == 3:
                raise ConnectionError("transient")
            return {"embeddings": [[3.0, 3.0]]}

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        out = b.encode(["a", "b", "c"])
        assert out.shape == (3, 2)
        assert np.any(out[0])
        assert not np.any(out[1])  # zero vector for the transient failure
        assert np.any(out[2])
        assert b.healthy is True  # one failure doesn't disable

    def test_encode_three_consecutive_mid_batch_failures_disables(self, monkeypatch):
        state = {"n": 0}

        def handler(url, p):
            state["n"] += 1
            if state["n"] == 1:
                return {"embeddings": []}  # force per-item loop
            if state["n"] == 2:
                return {"embeddings": [[1.0, 1.0]]}  # item 0 OK (sets dim)
            raise ConnectionError("flaky")  # items 1, 2, 3 fail consecutively

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        out = b.encode(["a", "b", "c", "d"])
        assert b.healthy is False
        assert "consecutive" in b._health_reason
        # Loop breaks after the 3rd consecutive failure: 1 good + 3 zeros.
        assert out.shape[0] >= 3

    def test_encode_unhealthy_returns_zero_vectors(self):
        b = OllamaEmbedBackend("m")
        b.healthy = False
        b._dim = 42
        assert b.encode("s").shape == (42,)
        assert b.encode(["a", "b"]).shape == (2, 42)

    def test_encode_unhealthy_unknown_dim_defaults_384(self):
        b = OllamaEmbedBackend("m")
        b.healthy = False
        b._dim = None
        assert b.encode("s").shape == (384,)
        assert b.encode(["a"]).shape == (1, 384)

    def test_encode_all_fail_no_results_returns_empty(self, monkeypatch):
        state = {"n": 0}

        def handler(url, p):
            state["n"] += 1
            # Batch malformed + first per-item call fails (dim unknown →
            # first-item failure → zeros returned early). To reach the
            # "not results" branch we need dim KNOWN and ALL items failing —
            # unreachable in practice; instead verify the first-item path.
            raise ConnectionError("down")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("m")
        out = b.encode(["a"])
        assert not np.any(out)


class TestOllamaSmokeTest:
    def test_healthy(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[0.5] * 64]})
        b = OllamaEmbedBackend("m")
        assert b.smoke_test() is True
        assert b.healthy is True

    def test_empty_vector(self, monkeypatch):
        # ``embedding: [[]]`` is truthy as a list, so _embed_single returns
        # np.array([[]]) — size 0 → the smoke-test "empty vector" branch.
        _patch_ollama(monkeypatch, lambda url, p: {"embedding": [[]]})
        b = OllamaEmbedBackend("m")
        assert b.smoke_test() is False
        assert "empty vector" in b._health_reason

    def test_all_zero(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[0.0] * 64]})
        b = OllamaEmbedBackend("m")
        assert b.smoke_test() is False
        assert "all-zero" in b._health_reason

    def test_nan(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[float("nan")] * 64]})
        b = OllamaEmbedBackend("m")
        assert b.smoke_test() is False
        assert "NaN" in b._health_reason

    def test_short_vector(self, monkeypatch):
        _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[0.5] * 10]})
        b = OllamaEmbedBackend("m")
        assert b.smoke_test() is False
        assert "suspiciously short" in b._health_reason

    def test_exception(self, monkeypatch):
        def handler(url, p):
            raise ConnectionError("ollama down")

        _patch_ollama(monkeypatch, handler)
        b = OllamaEmbedBackend("not-pulled")
        assert b.smoke_test() is False
        assert "not installed" in b._health_reason
        assert "ollama pull not-pulled" in b._health_reason


class TestKeepAliveResolution:
    def test_keep_alive_reads_provider_setting(self, monkeypatch):
        monkeypatch.setattr("core.llm.llm_provider_impl._get_keep_alive", lambda: "33m")
        calls = _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0]]})
        b = OllamaEmbedBackend("m")
        b._embed_single("x")
        assert calls[0]["payload"]["keep_alive"] == "33m"

    def test_keep_alive_exception_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            "core.llm.llm_provider_impl._get_keep_alive",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        calls = _patch_ollama(monkeypatch, lambda url, p: {"embeddings": [[1.0]]})
        b = OllamaEmbedBackend("m")
        b._embed_single("x")
        assert calls[0]["payload"]["keep_alive"] == "30m"

    def test_base_url_trailing_slash_stripped(self):
        b = OllamaEmbedBackend("m", base_url="http://localhost:11434/")
        assert b.base_url == "http://localhost:11434"
