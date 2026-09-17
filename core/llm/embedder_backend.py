"""V18.2.2: Embedder backend abstraction.

Supports two backends with a unified `.encode()` interface:

1. ``SentenceTransformerBackend`` — HuggingFace safetensors format
   (bge-small, bge-base, MiniLM, e5, nomic HF, etc.). Loads via
   sentence-transformers, runs locally, cached at
   ``~/.elixir/models/<name>/``.

2. ``OllamaEmbedBackend`` — GGUF format loaded via Ollama
   (Qwen3-Embedding-0.6B-GGUF, nomic-embed-text-v1.5-GGUF, etc.).
   Calls Ollama's ``/api/embeddings`` endpoint. The GGUF file must
   be registered as an Ollama model first (``ollama create``).

Both backends expose ``encode(texts) -> np.ndarray`` so callers don't
need to know which is active.

The backend is selected automatically based on the model name:
  - Ends in ``.gguf`` or contains ``:`` (Ollama naming) → Ollama
  - Otherwise → sentence-transformers

Or explicitly via ``settings.embedding.backend = "ollama"``.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any  # V18.20.3.12 (F821): used in annotations but was never imported

import numpy as np

logger = logging.getLogger(__name__)


class EmbedderUnavailable(RuntimeError):
    """V18.2.21: Raised when the embed backend is unhealthy or unavailable.

    Callers (content_judge, summarizer dedup) catch this to fall back to the
    Jaccard word-overlap similarity path EXPLICITLY — with a single loud
    WARNING — instead of silently receiving zero vectors and computing
    cos_sim(0, x) = 0 for every pair (the V18.2.20 root cause of
    "coverage=0% (0/46 claims)" and the 37-dropped-then-resurrected churn).
    """


# ── Backend 1: sentence-transformers (HF format) ───────────────────────────


class SentenceTransformerBackend:
    """Wraps a sentence-transformers model behind a uniform interface.

    V18.2.44 (Next Step #5): previously this wrapper was a thin pass-through
    with NO health flag and NO smoke-test. That meant a SentenceTransformer
    that *loaded* but silently produced zero / NaN vectors (CUDA OOM during
    the forward pass, corrupted safetensors, a device mismatch) would NOT
    be caught — ``is_embedder_healthy()`` returned ``True`` (``getattr``
    default), ``encode()`` didn't raise, and ``content_judge`` computed
    ``cos_sim(0, 0) = 0`` for every pair → the degenerate-0/N guard fired
    and Phase 2.2 (semantic fact-check) was silently SKIPPED.

    Now this backend mirrors ``OllamaEmbedBackend``: it has a ``.healthy``
    flag + ``smoke_test()`` (encodes ``"health check"`` and verifies a
    non-zero, non-NaN vector of reasonable dimension). ``get_embed_model()``
    runs the smoke-test on load; ``_semantic_similarity`` also checks the
    actual returned vectors defensively (defense-in-depth).
    """

    def __init__(self, model: Any) -> None:
        self._model = model
        # V18.2.44: health flag (matches OllamaEmbedBackend's API so
        # ``is_embedder_healthy()`` works uniformly for both backends).
        self.healthy: bool = True
        self._health_reason: str = ""

    def __getattr__(self, name: str) -> Any:
        """V18.2.44: delegate unknown attributes to the underlying model.

        Makes this wrapper a true drop-in replacement — callers that use
        ``model.get_sentence_embedding_dimension()`` etc. still work.
        ``__getattr__`` is only consulted when normal attribute lookup fails,
        so ``self.healthy`` / ``self._model`` / ``self.encode`` resolve here
        first and are NOT delegated.
        """
        return getattr(self._model, name)

    def encode(self, texts: str | Sequence[str], convert_to_numpy: bool = True,
               **kwargs) -> np.ndarray:
        """Encode via the underlying SentenceTransformer.

        V18.2.44: when this backend was marked unhealthy by ``smoke_test``,
        return ZERO VECTORS of the right shape (fail-safe, matches
        ``OllamaEmbedBackend`` V18.2.23 behavior). Callers that want the
        exception should check ``self.healthy`` proactively. This keeps
        callers like ``keypoints_builder`` (which don't catch
        ``EmbedderUnavailable``) from crashing, while the content_judge's
        degenerate-vector guard still trips the Jaccard fallback.
        """
        if not self.healthy:
            _dim = getattr(self._model, "get_sentence_embedding_dimension", lambda: 384)()
            try:
                _dim = int(_dim)
            except Exception:
                _dim = 384
            if isinstance(texts, str):
                return np.zeros(_dim, dtype=np.float32)
            return np.zeros((len(texts), _dim), dtype=np.float32)
        return self._model.encode(texts, convert_to_numpy=convert_to_numpy, **kwargs)

    def smoke_test(self) -> bool:
        """V18.2.44: probe the backend with a known-good string.

        Mirrors ``OllamaEmbedBackend.smoke_test``. Encodes ``"health check"``
        and verifies the result is a non-zero, non-NaN vector of reasonable
        dimension (>=32). If the call raises OR returns a degenerate vector,
        marks the backend unhealthy and returns ``False``.

        This catches the V18.2.43 regression where ``all-MiniLM-L6-v2``
        loaded successfully but produced zero vectors on the user's RTX 3060
        (a CUDA forward-pass OOM that SentenceTransformer swallows into a
        zero tensor instead of raising).
        """
        try:
            vec = self._model.encode("health check", convert_to_numpy=True,
                                     show_progress_bar=False)
            arr = np.asarray(vec, dtype=np.float32).ravel()
            if arr.size == 0:
                self.healthy = False
                self._health_reason = "smoke-test returned an empty vector"
            elif not np.any(arr):
                self.healthy = False
                self._health_reason = "smoke-test returned an all-zero vector (CUDA forward-pass OOM suspected)"
            elif np.isnan(arr).any():
                self.healthy = False
                self._health_reason = "smoke-test returned a NaN vector"
            elif arr.shape[0] < 32:
                self.healthy = False
                self._health_reason = (
                    f"smoke-test returned a suspiciously short vector (dim={arr.shape[0]})"
                )
            else:
                self.healthy = True
                self._health_reason = ""
        except Exception as exc:
            self.healthy = False
            self._health_reason = (
                f"smoke-test raised {type(exc).__name__}: {exc}"
            )
        if not self.healthy:
            logger.error(
                "SentenceTransformer smoke-test FAILED: %s. Semantic "
                "similarity will fall back to Jaccard word overlap (weaker "
                "signal). Phase 2.2 fact-check will still run on Jaccard.",
                self._health_reason,
            )
        return self.healthy


# ── Backend 2: Ollama (GGUF format) ────────────────────────────────────────


class OllamaEmbedBackend:
    """Embedder backend that calls Ollama's ``/api/embeddings`` endpoint.

    For GGUF embedding models (e.g. Qwen3-Embedding-0.6B-GGUF). The user
    must register the GGUF as an Ollama model first:

        ollama create qwen3-embed -f Modelfile

    where Modelfile contains:
        FROM ./Qwen3-Embedding-0.6B-Q8_0.gguf
        PARAMETER temperature 0

    Then set ``settings.embedding.model = "qwen3-embed"`` (the Ollama name,
    not the GGUF filename).

    Ollama's legacy ``/api/embeddings`` endpoint returns one vector per call;
    since V18.20.2.0 (SWOT A22) the batch ``encode()`` first tries the NEW
    ``/api/embed`` endpoint with the whole list as one request (and falls
    back to the sequential per-item loop on any batch failure). For a
    typical chapter (~50 source sentences) this is one HTTP call instead
    of ~50 — a few seconds saved per chapter.
    """

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434",
                 timeout: int = 60) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Cache the embedding dimension after the first call
        self._dim: int | None = None
        # V18.2.21 (BUG-1/2/3 fix): health flag. Set False by the singleton's
        # smoke-test if the backend returns all-zero vectors or raises on a
        # known-good probe string. When False, encode() raises immediately
        # instead of silently returning zero vectors that poison every
        # downstream similarity check (the root cause of the V18.2.20
        # "coverage=0% (0/46 claims)" + "dropped 37 then resurrected 37"
# churn seen in a rig conversion log).
        self.healthy: bool = True
        self._health_reason: str = ""

    def _keep_alive(self) -> str:
        """V18.20.2.0 (SWOT A22): the embedder's keep_alive policy.

        Same single source as the main model: ``_get_keep_alive()`` from
        ``core.llm.llm_provider_impl`` (settings ``llm.keep_alive``, default
        "30m"). The old embed payload had NO keep_alive, so Ollama used its
        default 5m idle unload for the embedder while the main model held
        30m — interleaving generate and embed phases on a 12 GB card caused
        embedder reload thrash between phases. Fallback "30m" when the
        settings layer is unavailable (matches the provider's own fallback).
        """
        try:
            from core.llm.llm_provider_impl import _get_keep_alive
            return _get_keep_alive()
        except Exception:
            return "30m"

    def _embed_single(self, text: str) -> np.ndarray:
        """Call Ollama /api/embed (new) with fallback to /api/embeddings (old)."""
        from utils.network import safe_ollama_request
        # V18.2.19: Try the NEW /api/embed endpoint first (Ollama 0.1.34+).
        # The OLD /api/embeddings returns 404 on newer Ollama versions, causing
        # the hundreds of "Ollama embed batch item N failed: 404 Client Error"
        # warnings seen in the conversion log. /api/embed is the current
        # standard; /api/embeddings is the legacy single-text endpoint.
        for endpoint, payload_key in [
            ("/api/embed", "input"),       # NEW: {"model":..., "input": text}
            ("/api/embeddings", "prompt"), # OLD: {"model":..., "prompt": text}
        ]:
            url = f"{self.base_url}{endpoint}"
            # V18.20.2.0 (SWOT A22): keep_alive — stops the 5m-default idle
            # eviction of the embedder between phases (see _keep_alive).
            payload = {
                "model": self.model_name,
                payload_key: text,
                "keep_alive": self._keep_alive(),
            }
            try:
                resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
                data = resp.json()
                # /api/embed returns {"embeddings": [[...]]} (list of lists)
                # /api/embeddings returns {"embedding": [...]} (single list)
                vec = data.get("embedding") or data.get("embeddings", [[]])[0]
                if vec:
                    arr = np.array(vec, dtype=np.float32)
                    if self._dim is None:
                        self._dim = len(arr)
                    return arr
            except Exception as exc:
                # 404 → try the next endpoint; other errors → propagate
                if "404" in str(exc) or "Not Found" in str(exc):
                    logger.debug("Ollama %s returned 404, trying next endpoint", endpoint)
                    continue
                raise
        raise RuntimeError(f"Both Ollama embed endpoints failed for model '{self.model_name}'")

    def _embed_batch(self, texts: Sequence[str]) -> list | None:
        """V18.20.2.0 (SWOT A22): encode the WHOLE list in ONE /api/embed call.

        Ollama's /api/embed (0.1.34+) accepts ``"input": [list, of, texts]``
        and returns ``{"embeddings": [[...], ...]}``. The old encode() looped
        one HTTP call per text (~50 sequential calls per chapter — the miss
        list is already grouped by embedding_cache.cached_encode).

        Returns the list of vectors, or ``None`` when the batched call fails
        or returns a count-mismatched/malformed response — the caller then
        falls back to the existing per-item loop so partial failures degrade
        gracefully and the zero-vector semantics are unchanged.

        The legacy /api/embeddings endpoint only accepts a single input, so
        batching is NOT attempted there (the per-item loop covers it).
        """
        from utils.network import safe_ollama_request
        url = f"{self.base_url}/api/embed"
        payload = {
            "model": self.model_name,
            "input": list(texts),
            "keep_alive": self._keep_alive(),
        }
        try:
            resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
            data = resp.json()
            embs = data.get("embeddings")
            if not isinstance(embs, list) or len(embs) != len(texts):
                logger.debug(
                    "Ollama batched /api/embed returned %s vectors for %d texts "
                    "— falling back to per-item",
                    "malformed" if not isinstance(embs, list) else len(embs),
                    len(texts),
                )
                return None
            vecs = []
            for v in embs:
                if not v:
                    return None  # any empty vector → per-item fallback
                arr = np.array(v, dtype=np.float32)
                if self._dim is None:
                    self._dim = len(arr)
                vecs.append(arr)
            return vecs
        except Exception as exc:
            logger.debug(
                "Ollama batched /api/embed failed (%s: %s) — falling back to per-item",
                type(exc).__name__, exc,
            )
            return None

    def encode(self, texts: str | Sequence[str], convert_to_numpy: bool = True,
               **kwargs) -> np.ndarray:
        """Encode text(s) via Ollama. Returns a numpy array.

        For a single string: returns a 1-D array (dim,).
        For a list of strings: returns a 2-D array (n, dim).

        V18.2.21 (BUG-1/2/3 fix): if this backend was marked unhealthy by
        the singleton's smoke-test, ``encode()`` logs a WARNING and returns
        ZERO VECTORS of the right shape. This is fail-SAFE (callers that
        do ``encode([bp])[0]`` don't crash with TypeError) while still
        being observable (the smoke-test logged an ERROR once at load
        time, and the content_judge's degenerate-0/N guard catches the
        downstream effect).

        V18.2.23 (BUG-B regression fix): V18.2.21 made encode() RAISE
        EmbedderUnavailable when unhealthy. This was too aggressive —
        keypoints_builder.py:130 and 5+ other callers call encode()
        without catching the exception, causing a FATAL crash AFTER the
        summary completed successfully (the user lost all keypoints
        output). Now encode() returns zero vectors (fail-safe) instead of
        raising. Callers that want the exception (to trigger a Jaccard
        fallback) should check ``self.healthy`` proactively or call
        ``encode_strict()``.
        """
        if not self.healthy:
            # V18.2.23: return zero vectors (fail-safe), NOT raise.
            # The smoke-test already logged an ERROR at load time.
            # Raising here crashes callers like keypoints_builder that
            # don't catch EmbedderUnavailable.
            if isinstance(texts, str):
                dim = self._dim or 384  # 384 = MiniLM/bge-small default
                return np.zeros(dim, dtype=np.float32)
            dim = self._dim or 384
            n = len(texts)
            return np.zeros((n, dim), dtype=np.float32)
        if isinstance(texts, str):
            return self._embed_single(texts)

        _texts = list(texts)
        if not _texts:
            return np.array([], dtype=np.float32)

        # V18.20.2.0 (SWOT A22): BATCHED fast path — one /api/embed request
        # with the whole miss-list as "input": [list] (the endpoint accepts
        # a list since Ollama 0.1.34). N-fold fewer HTTP round-trips per
        # chapter (~50 → 1). On ANY batch failure (endpoint 404 on old
        # Ollama, timeout, count mismatch) we fall through to the existing
        # per-item loop below — partial failures degrade gracefully and the
        # zero-vector behavior is NOT made worse.
        _batched = self._embed_batch(_texts)
        if _batched is not None:
            return np.array(_batched, dtype=np.float32)

        # Batch — Ollama /api/embeddings is single-text, so loop.
        # (A future Ollama version may add /api/embed for true batching.)
        #
        # V18.2.23 (BUG-B regression fix): if the FIRST item fails (we don't
        # yet know the dimension), mark the backend unhealthy + log ERROR +
        # return ZERO VECTORS (not raise). V18.2.21 raised here, which crashed
        # callers like keypoints_builder.py that don't catch the exception.
        # Now the smoke-test + first-call-failure both set healthy=False and
        # return zeros, so callers get a degraded result instead of a crash.
        # The content_judge's degenerate-0/N guard catches the downstream effect.
        results = []
        consecutive_failures = 0
        for i, t in enumerate(_texts):
            try:
                vec = self._embed_single(t)
                results.append(vec)
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                if i == 0 or self._dim is None:
                    # First-call failure → model not installed / wrong name.
                    # Mark unhealthy + log ERROR. Return zero vectors (fail-safe)
                    # instead of raising (which crashed keypoints_builder).
                    self.healthy = False
                    self._health_reason = (
                        f"first encode failed ({type(exc).__name__}: {exc}). "
                        f"Likely the model '{self.model_name}' is not pulled in "
                        f"Ollama. Run: ollama pull {self.model_name}"
                    )
                    logger.error(
                        "Ollama embed backend FAILED on first item — model '%s' "
                        "likely not installed. %s. Disabling backend; returning "
                        "zero vectors for this batch. Semantic similarity will "
                        "be degraded (cos_sim=0 for all pairs).",
                        self.model_name, exc,
                    )
                    # Return zero vectors for the whole batch (fail-safe).
                    dim = 384  # MiniLM/bge-small default; unknown since first call failed
                    return np.zeros((len(_texts), dim), dtype=np.float32)
                # Mid-batch transient failure → zero vector (dim known)
                logger.warning("Ollama embed batch item %d failed: %s: %s",
                               i, type(exc).__name__, exc)
                results.append(np.zeros(self._dim, dtype=np.float32))
                if consecutive_failures >= 3:
                    self.healthy = False
                    self._health_reason = (
                        f"{consecutive_failures} consecutive mid-batch failures "
                        f"(last: {type(exc).__name__}: {exc})"
                    )
                    logger.error(
                        "Ollama embed backend marked unhealthy after %d "
                        "consecutive failures. Disabling for this run.",
                        consecutive_failures,
                    )
                    break

        if not results:
            return np.array([], dtype=np.float32)

        return np.array(results, dtype=np.float32)

    def smoke_test(self) -> bool:
        """V18.2.21 (BUG-1/2/3 fix): probe the backend with a known-good string.

        Encodes ``"health check"`` and verifies the result is a non-zero,
        non-NaN vector of reasonable dimension (>=32). If the call raises OR
        returns a degenerate vector, marks the backend unhealthy and returns
        False. Called once by ``get_embed_model()`` after construction so the
        first real ``encode()`` call never silently fails.
        """
        try:
            vec = self._embed_single("health check")
            arr = np.asarray(vec, dtype=np.float32)
            if arr.size == 0:
                self.healthy = False
                self._health_reason = "smoke-test returned an empty vector"
            elif not np.any(arr):
                self.healthy = False
                self._health_reason = "smoke-test returned an all-zero vector"
            elif np.isnan(arr).any():
                self.healthy = False
                self._health_reason = "smoke-test returned a NaN vector"
            elif arr.ndim == 1 and arr.shape[0] < 32:
                self.healthy = False
                self._health_reason = (
                    f"smoke-test returned a suspiciously short vector (dim={arr.shape[0]})"
                )
            else:
                self.healthy = True
                self._health_reason = ""
        except Exception as exc:
            self.healthy = False
            self._health_reason = (
                f"smoke-test raised {type(exc).__name__}: {exc}. "
                f"Likely '{self.model_name}' is not installed in Ollama. "
                f"Run: ollama pull {self.model_name}"
            )
        if not self.healthy:
            logger.error(
                "Embedder smoke-test FAILED for '%s': %s. Semantic similarity "
                "will fall back to Jaccard word overlap (weaker signal). %s",
                self.model_name, self._health_reason,
                "" if "not installed" not in self._health_reason else "",
            )
        return self.healthy


# ── Backend selector ────────────────────────────────────────────────────────


def is_ollama_embed_model(model_name: str) -> bool:
    """Heuristic: does this model name look like an Ollama/GGUF model?

    Ollama models typically:
    - Don't contain "/" (HF org/name format uses "/")
    - May end in ":latest" or ":tag"
    - May end in ".gguf"
    - May be a single word like "qwen3-embed"
    """
    if not model_name:
        return False
    low = model_name.lower()
    # HF format: "BAAI/bge-base-en-v1.5"
    if "/" in model_name and not low.endswith(".gguf"):
        return False
    # GGUF file
    if low.endswith(".gguf"):
        return True
    # Ollama-tagged: "qwen3-embed:latest"
    if ":" in model_name:
        return True
    # Bare Ollama name (no path, no HF prefix)
    # Conservative: only treat as Ollama if it's a single token without dots
    # (HF models like "all-MiniLM-L6-v2" have dots and are HF-hosted)
    if "." not in model_name and "/" not in model_name:
        return True
    return False


def create_embedder(model_name: str, base_url: str = "http://localhost:11434") -> Any:
    """Create the right embedder backend for a model name.

    Returns an object with an ``.encode(texts)`` method (either
    SentenceTransformerBackend or OllamaEmbedBackend).
    """
    if is_ollama_embed_model(model_name):
        logger.info("Using Ollama embedder backend for '%s' (GGUF/Ollama model)", model_name)
        return OllamaEmbedBackend(model_name, base_url=base_url)
    # Fall through to sentence-transformers (loaded by the caller via get_embed_model)
    return None  # signal: use the sentence-transformers path


__all__ = [
    "SentenceTransformerBackend",
    "OllamaEmbedBackend",
    "is_ollama_embed_model",
    "create_embedder",
]
