"""V18.2.23 (BUG-B regression) — Tests that encode() NEVER raises.

V18.2.21 made OllamaEmbedBackend.encode() RAISE EmbedderUnavailable when
unhealthy. This crashed callers like keypoints_builder.py:130 that call
``encode([bp])[0]`` without catching the exception — the conversion crashed
AFTER the summary completed, losing all keypoints output.

V18.2.23 fixes this: encode() now returns ZERO VECTORS (fail-safe) instead
of raising. The smoke-test still logs an ERROR at load time, and the
content_judge's degenerate-0/N guard catches the downstream effect.

These tests verify encode() NEVER raises, regardless of health state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np

from core.llm.embedder_backend import EmbedderUnavailable, OllamaEmbedBackend


class TestEncodeNeverRaises:
    """encode() must NEVER raise — it returns zero vectors when unhealthy."""

    def _make_unhealthy_backend(self) -> OllamaEmbedBackend:
        """Create an OllamaEmbedBackend marked unhealthy (smoke-test failed)."""
        backend = OllamaEmbedBackend("all-MiniLM-L6-v2")
        backend.healthy = False
        backend._health_reason = "smoke-test raised RuntimeError: not installed"
        backend._dim = 384  # pretend we know the dim
        return backend

    def test_encode_single_string_returns_zeros_not_raise(self):
        """Single-string encode on unhealthy backend → zero vector, not raise."""
        backend = self._make_unhealthy_backend()
        result = backend.encode("test text")
        assert isinstance(result, np.ndarray)
        assert np.all(result == 0.0)
        assert result.shape == (384,)

    def test_encode_list_returns_zeros_not_raise(self):
        """Batch encode on unhealthy backend → zero matrix, not raise."""
        backend = self._make_unhealthy_backend()
        result = backend.encode(["bullet 1", "bullet 2", "bullet 3"])
        assert isinstance(result, np.ndarray)
        assert result.shape == (3, 384)
        assert np.all(result == 0.0)

    def test_encode_single_no_dim_returns_zeros(self):
        """Single-string encode when dim unknown → still zeros (default 384)."""
        backend = OllamaEmbedBackend("all-MiniLM-L6-v2")
        backend.healthy = False
        backend._dim = None  # dim unknown
        result = backend.encode("test")
        assert isinstance(result, np.ndarray)
        assert np.all(result == 0.0)
        assert result.shape == (384,)

    def test_encode_batch_no_dim_returns_zeros(self):
        """Batch encode when dim unknown → zero matrix (default 384)."""
        backend = OllamaEmbedBackend("all-MiniLM-L6-v2")
        backend.healthy = False
        backend._dim = None
        result = backend.encode(["a", "b"])
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 384)
        assert np.all(result == 0.0)

    def test_encode_does_not_raise_embedder_unavailable(self):
        """The V18.2.21 regression: encode() raised EmbedderUnavailable.
        V18.2.23 fix: it must NOT raise — return zeros instead."""
        backend = self._make_unhealthy_backend()
        # This must NOT raise EmbedderUnavailable
        try:
            result = backend.encode(["test"])
            assert result is not None
        except EmbedderUnavailable:
            pytest.fail(
                "encode() raised EmbedderUnavailable on unhealthy backend — "
                "this is the V18.2.21 regression that crashed keypoints_builder. "
                "encode() must return zero vectors, not raise."
            )

    def test_keypoints_builder_pattern_safe(self):
        """Simulate the keypoints_builder.py:130 pattern: encode([bp])[0].

        This must NOT crash even when the backend is unhealthy.
        """
        backend = self._make_unhealthy_backend()
        # keypoints_builder.py:130 does: bp_embedding = _embed_model.encode([bp], convert_to_numpy=True)[0]
        bp_embedding = backend.encode(["some bullet point"], convert_to_numpy=True)[0]
        assert bp_embedding is not None
        assert isinstance(bp_embedding, np.ndarray)
        # It's a zero vector, but it doesn't crash
        assert np.all(bp_embedding == 0.0)


class TestIsEmbedderHealthy:
    """Test the is_embedder_healthy() helper."""

    def test_returns_false_when_no_model_loaded(self):
        """When no embed model has been loaded, returns False."""
        from core.llm import model_singletons

        # Reset the singleton
        old = model_singletons._embed_model
        model_singletons._embed_model = None
        try:
            assert model_singletons.is_embedder_healthy() is False
        finally:
            model_singletons._embed_model = old

    def test_returns_true_for_healthy_ollama_backend(self):
        """When an OllamaEmbedBackend is loaded and healthy, returns True."""
        from core.llm import model_singletons

        backend = OllamaEmbedBackend("test-model")
        backend.healthy = True
        old = model_singletons._embed_model
        model_singletons._embed_model = backend
        try:
            assert model_singletons.is_embedder_healthy() is True
        finally:
            model_singletons._embed_model = old

    def test_returns_false_for_unhealthy_ollama_backend(self):
        """When an OllamaEmbedBackend is loaded but unhealthy, returns False."""
        from core.llm import model_singletons

        backend = OllamaEmbedBackend("test-model")
        backend.healthy = False
        old = model_singletons._embed_model
        model_singletons._embed_model = backend
        try:
            assert model_singletons.is_embedder_healthy() is False
        finally:
            model_singletons._embed_model = old

    def test_returns_true_for_sentence_transformer(self):
        """SentenceTransformer backends don't have .healthy → assumed True."""
        from core.llm import model_singletons

        mock_st = MagicMock()  # no .healthy attribute
        del mock_st.healthy  # ensure AttributeError
        old = model_singletons._embed_model
        model_singletons._embed_model = mock_st
        try:
            assert model_singletons.is_embedder_healthy() is True
        finally:
            model_singletons._embed_model = old


class TestSemanticDedupSkipsWhenUnhealthy:
    """The dedup must skip (return bullets unchanged) when embedder unhealthy."""

    def test_dedup_checks_health_before_encoding(self):
        """Verify the source code checks is_embedder_healthy before encode.

        V18.7: _semantic_dedup_bullets was extracted to summary_validator.py.
        The check now lives there, not in summarizer.py.
        """
        sv_path = _project_root / "core" / "summarisation" / "summary_validator.py"
        content = sv_path.read_text(encoding="utf-8")
        assert "is_embedder_healthy" in content, (
            "_semantic_dedup_bullets must check is_embedder_healthy (in summary_validator.py)"
        )
        # The check must come BEFORE the encode call
        health_check_idx = content.find("if not is_embedder_healthy():")
        encode_idx = content.find("embed_model.encode(bullet_strs", health_check_idx)
        assert encode_idx > health_check_idx, (
            "is_embedder_healthy check must come before encode call in dedup"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
