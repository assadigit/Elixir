"""V10.31.0 (Sprint 4.6): Singleton model loaders for shared ML models.

Before V10.31.0, ``SentenceTransformer('all-MiniLM-L6-v2')`` was loaded
**11 separate times** across 6 files (content_judge, keypoints_builder,
text_preprocessor, advanced_validator, packets, translation/validator).
The V10.27.0 audit found that ``KeypointsBuilder`` alone reloaded the
model on every call — **20 reloads for a 20-chapter book**, each taking
~3 seconds and ~400 MB of RAM (90 MB weights + KV cache).  ``spacy.load``
had the same problem (4 sites).

This module provides lazy module-level singletons so every call site
shares one instance:

    from core.llm.model_singletons import get_embed_model, get_spacy_nlp
    model = get_embed_model()          # loads on first call, returns same instance after
    nlp = get_spacy_nlp("en_core_web_sm")  # one per model name

The singletons are **lazy** (not loaded at import time) so importing this
module is free — the model only loads when first requested.  This matters
because ``core.llm`` is imported at startup, and loading sentence-transformers
at startup would add 3 seconds to app launch.

Thread-safety: the getters use a lock so concurrent first-calls (e.g. from
the ThreadPoolExecutor summariser) don't double-load.

V15.0.0 changes:
  - ``get_embed_model()`` now uses a **persistent local model directory**
    (``~/.elixir/models/<model_name>/``) so the model is downloaded
    only ONCE and then loaded from disk (100% offline) on every subsequent
    launch.
  - A 60-second download timeout prevents the 15-minute hang that occurred
    when the HuggingFace hub was slow or unreachable. On timeout the model
    returns ``None`` (graceful degradation — semantic features disabled but
    the app keeps running).
  - V18.20.4.12 (W-c17): ``HF_HUB_OFFLINE`` / ``TRANSFORMERS_OFFLINE`` are
    scoped to the offline from-disk load ONLY — snapshotted before, set to
    ``"1"``, and restored afterwards on success AND on failure.  (They
    used to stay set for the rest of the session after a successful load,
    silently forcing any LATER HuggingFace network access in-process —
    e.g. downloading a different model — offline.)
  - Added the missing ``from pathlib import Path`` import — this also
    fixes the ``NameError: name 'Path' is not defined`` crash that V13.45.5
    hit inside ``_semantic_dedup_bullets()`` (Improvement 3).
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Singletons (lazy) ───────────────────────────────────────────────────────

_embed_model: Any | None = None
_embed_model_name: str | None = None
# V18.2.37b: module-level flag for forcing embedder to CPU when IQ2_XXS
# is active. Set by is_embedder_healthy() — checked by _resolve_embed_device().
_FORCE_CPU_EMBEDDER: bool = False
_spacy_nlp_cache: dict[str, Any] = {}
_lock = threading.Lock()

# V15.0.0: how long we wait for a fresh SentenceTransformer download before
# giving up and returning None (graceful degradation).  60 seconds is long
# enough for a normal first download on a reasonable connection, but short
# enough that the app never appears frozen for 15 minutes.
# V18.15: Raised from 60s to 300s (5 min). The V18.14.x logs showed the
# embedder was always "unhealthy" — the 60s timeout was too short for
# HuggingFace downloads on slower connections. 300s gives enough time
# for the ~130MB bge-small-en-v1.5 model to download on a moderate
# connection. The user explicitly requested: "make it download from
# internet if cached version wasn't available (on the first run)."
_EMBED_DOWNLOAD_TIMEOUT_SECONDS = 300


# ── V18.20.4.12 (W-c17): offline-env snapshot/restore ──────────────────────
#
# The from-disk load in ``get_embed_model`` sets HF_HUB_OFFLINE /
# TRANSFORMERS_OFFLINE so the SentenceTransformer constructor can never
# phone home for a model we already have on disk.  The flags used to stay
# set process-wide after a successful load, which silently forced ALL
# later HuggingFace network access in-process (e.g. downloading a
# different model) offline.  These helpers scope the flags to the load:
# snapshot the prior state, set, restore afterwards — success or failure.


def _snapshot_offline_env() -> dict:
    """Capture the current values of the two HuggingFace offline env vars.

    Returns ``{key: prior_value_or_None}`` — ``None`` means "was unset".
    """
    return {
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
    }


def _restore_offline_env(snapshot: dict) -> None:
    """Restore the offline env vars captured by ``_snapshot_offline_env``.

    Keys that were previously unset are removed (popped); keys that had a
    prior value are restored to it — the user's own environment survives a
    failed load untouched.  (The pre-V18.20.4.12 failure path popped the
    keys unconditionally, which also CLOBBERED a user-set value.)
    """
    for _key, _prior in snapshot.items():
        if _prior is None:
            os.environ.pop(_key, None)
        else:
            os.environ[_key] = _prior


def _resolve_embed_device() -> str:
    """V18.1 (O3): Resolve the embedding model device from settings.

    Reads ``settings.embedding.device``:
      - ``"auto"``  → cuda if available AND VRAM headroom > 1 GB, else cpu
      - ``"cuda"``  → cuda (falls back to cpu if unavailable)
      - ``"cpu"``   → cpu

    The 1 GB headroom check for ``auto`` prevents the embedder from
    competing with the summarization LLM on low-VRAM cards (12 GB RTX 3060
    with a 27B model leaves <1 GB free). On such cards, the embedder
    stays on CPU — MiniLM/bge-base on CPU is ~1-3s per batch, acceptable.

    For sequential load mode (``settings.embedding.load_mode="sequential"``),
    the caller is expected to unload the LLM first, so ``auto`` will
    always pick cuda (the VRAM is free at that point). This function
    doesn't enforce that — it just reports current free VRAM.
    """
    try:
        from utils.settings import Settings
        device_pref = Settings().get("embedding.device", "auto")
    except Exception:
        device_pref = "auto"

    if device_pref == "cpu":
        return "cpu"

    if device_pref == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        logger.warning("embedding.device='cuda' but CUDA unavailable — falling back to cpu")
        return "cpu"

    # "auto" — check VRAM headroom
    # V18.2.37b: check the module-level flag first — set by is_embedder_healthy()
    # when IQ2_XXS is detected. This avoids VRAM conflict with the 10.2GB LLM.
    if _FORCE_CPU_EMBEDDER:
        logger.info("V18.2.37b: embedder forced to CPU (IQ2_XXS model active)")
        return "cpu"
    try:
        import torch
        if not torch.cuda.is_available():
            return "cpu"
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)
        free_gb = total_gb - allocated_gb
        # V18.2 (audit): Lowered threshold 1.5→0.6 GB. The V18.1 threshold of
        # 1.5 GB was too conservative — it kept the embedder on CPU even when
        # there was enough free VRAM for bge-base (440 MB). With IQ2_XXS
        # (9 GB model), there's ~0.6-1.0 GB free, which is enough for bge-base
        # or MiniLM on GPU. The 0.6 GB threshold = embedder size (0.44 GB) +
        # 0.16 GB safety buffer.
        if free_gb > 0.6:
            return "cuda"
        logger.info(
            "embedding device=auto: only %.1f GB VRAM free (%.1f/%.1f used) — "
            "embedder stays on CPU to avoid LLM competition",
            free_gb, allocated_gb, total_gb,
        )
        return "cpu"
    except ImportError:
        return "cpu"
    except Exception as exc:
        logger.debug("embed device auto-detect failed: %s: %s", type(exc).__name__, exc)
        return "cpu"


def get_embed_model(model_name: str = "") -> Any | None:
    """Return a shared embedder instance (lazy singleton).

    V18.2.2 (audit) — **multi-backend support + configurable model + GPU
    auto-placement + on-disk embedding cache**.

    Model resolution order:
      1. If ``model_name`` is passed explicitly, use it.
      2. Otherwise read ``settings.embedding.model`` (default:
         ``nomic-embed-text`` — V18.15.1 default, uses Ollama's
         ``/api/embeddings`` endpoint. Just needs ``ollama pull
         nomic-embed-text``. No sentence_transformers needed.)

    Backend selection (V18.2.2):
      - If the model name looks like an Ollama/GGUF model (e.g.
        ``qwen3-embed``, ``Qwen3-Embedding-0.6B-Q8_0.gguf``, ``nomic:latest``)
        → uses :class:`OllamaEmbedBackend` which calls Ollama's
        ``/api/embeddings`` endpoint. The GGUF must be registered as an
        Ollama model first (``ollama create``).
      - Otherwise → uses ``sentence-transformers`` (HF safetensors format,
        cached at ``~/.elixir/models/<name>/``).

    Device resolution (``settings.embedding.device``, HF backend only):
      - ``"auto"``  — cuda if available AND VRAM headroom > 0.6 GB, else CPU
      - ``"cuda"``  — force GPU (falls back to CPU if unavailable)
      - ``"cpu"``   — force CPU

    V15.0.0 persistent local cache + 60s download timeout + offline mode
    remain in effect for the HF backend.

    Returns ``None`` if the backend can't be initialized. Callers must
    handle ``None`` gracefully.
    """
    # V18.1: resolve model name from settings if not passed explicitly
    if not model_name:
        try:
            from utils.settings import Settings
            model_name = Settings().get("embedding.model", "nomic-embed-text")
        except Exception:
            model_name = "nomic-embed-text"

    global _embed_model, _embed_model_name
    if _embed_model is not None and _embed_model_name == model_name:
        return _embed_model
    with _lock:
        # Double-checked locking
        if _embed_model is not None and _embed_model_name == model_name:
            return _embed_model

        # V18.2.2: If this looks like an Ollama/GGUF model, use the Ollama backend.
        # This supports Qwen3-Embedding-0.6B-GGUF, nomic-embed-text-v1.5-GGUF, etc.
        try:
            from core.llm.embedder_backend import OllamaEmbedBackend, is_ollama_embed_model
            if is_ollama_embed_model(model_name):
                logger.info("Loading Ollama embedder backend: %s", model_name)
                try:
                    from utils.settings import Settings
                    _ollama_url = Settings().get("llm.ollama_url", "http://localhost:11434")
                except Exception:
                    _ollama_url = "http://localhost:11434"
                _embed_model = OllamaEmbedBackend(model_name, base_url=_ollama_url)
                _embed_model_name = model_name
                # V18.2.21 (BUG-1/2/3 fix): smoke-test the backend ONCE on load.
                # If the model isn't pulled in Ollama (or returns degenerate
                # vectors), mark it unhealthy so encode() raises immediately
                # instead of silently returning zeros that poison every
                # downstream cos_sim. The V18.2.20 "coverage=0% (0/46)" bug
                # was caused by exactly this: 76+ batch-item warnings, each
                # returning a zero vector, with no health flag.
                _embed_model.smoke_test()
                return _embed_model
        except Exception as exc:
            logger.debug("Ollama embedder backend check failed: %s: %s", type(exc).__name__, exc)

        # V15.0.0: persistent local model directory.
        # Model name ``all-MiniLM-L6-v2`` → dir ``all-MiniLM-L6-v2``.
        # (Slash-separated repo ids like ``org/model`` would map to
        # ``org--model`` to stay a single directory, but the default model
        # has no slash so this is a no-op for it.)
        _model_dir = Path.home() / ".elixir" / "models" / model_name.replace("/", "--")
        _is_saved = (_model_dir / "config.json").exists() or (
            _model_dir / "model_config.json"
        ).exists()

        if _is_saved:
            # Load from disk — 100% offline, instant.
            # V18.20.4.12 (W-c17): the offline flags are scoped to THIS load
            # (snapshot → set → restore in ``finally``).  They used to stay
            # set process-wide after success, silently forcing all later
            # HuggingFace network access offline for the rest of the session.
            _offline_snapshot = _snapshot_offline_env()
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            try:
                from sentence_transformers import SentenceTransformer

                # V18.1 (O3): resolve device from settings
                _device = _resolve_embed_device()
                logger.info(
                    "Loading SentenceTransformer from local cache (offline): %s [device=%s]",
                    _model_dir, _device,
                )
                _embed_model = SentenceTransformer(str(_model_dir), device=_device)
                _embed_model_name = model_name
                # V18.2.44 (Next Step #5): wrap in SentenceTransformerBackend
                # and run smoke_test so a silently-broken model (zero/NaN
                # vectors from a CUDA forward-pass OOM) is detected at load
                # time, not after it has poisoned every cos_sim downstream.
                from core.llm.embedder_backend import SentenceTransformerBackend
                _wrapped = SentenceTransformerBackend(_embed_model)
                if not _wrapped.smoke_test():
                    logger.warning(
                        "V18.2.44: SentenceTransformerBackend smoke-test FAILED "
                        "for '%s' (%s). Semantic similarity will fall back to "
                        "Jaccard; Phase 2.2 fact-check still runs on Jaccard.",
                        model_name, _wrapped._health_reason,
                    )
                _embed_model = _wrapped
                return _embed_model
            except Exception as exc:
                # Fall through to the download path if disk load fails —
                # the cached copy may be corrupt or from an incompatible
                # sentence-transformers version.
                logger.warning(
                    "Failed to load local model from %s: %s: %s — attempting fresh download",
                    _model_dir, type(exc).__name__, exc,
                )
                # The offline flags are restored by the ``finally`` below, so
                # the download path is NOT forced offline — and the user's
                # own pre-existing flags (if any) survive the failure.
            finally:
                # V18.20.4.12 (W-c17): restore the prior env state on BOTH
                # paths — success (the ``return`` above) and failure (the
                # ``except`` above falls through to the download path).
                _restore_offline_env(_offline_snapshot)

        # Not saved locally (or disk load failed) — try a fresh download.
        # V18.15: Added a retry — if the first download attempt fails (timeout
        # or error), retry once. The user explicitly requested: "make it
        # download from internet if cached version wasn't available (on the
        # first run)." The 300s timeout + retry ensures the model downloads
        # even on slower connections.
        try:
            import concurrent.futures

            from sentence_transformers import SentenceTransformer

            _device = _resolve_embed_device()

            # V18.15: retry loop — try up to 2 times
            for _attempt in range(2):
                _attempt_label = f" (attempt {_attempt + 1}/2)" if _attempt > 0 else ""
                logger.info(
                    "Downloading SentenceTransformer('%s') (timeout=%ds, one-time)%s [device=%s]...",
                    model_name, _EMBED_DOWNLOAD_TIMEOUT_SECONDS, _attempt_label, _device,
                )
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            lambda: SentenceTransformer(model_name, device=_device)
                        )
                        _embed_model = future.result(timeout=_EMBED_DOWNLOAD_TIMEOUT_SECONDS)
                    break  # success — exit the retry loop
                except concurrent.futures.TimeoutError:
                    if _attempt == 0:
                        logger.warning(
                            "SentenceTransformer('%s') download timed out after %ds — "
                            "retrying once more...",
                            model_name, _EMBED_DOWNLOAD_TIMEOUT_SECONDS,
                        )
                        continue
                    logger.warning(
                        "SentenceTransformer('%s') download timed out after %ds (2 attempts) — "
                        "semantic features disabled. Run the app once with internet "
                        "to seed the persistent local model at %s",
                        model_name, _EMBED_DOWNLOAD_TIMEOUT_SECONDS, _model_dir,
                    )
                    return None
                except Exception as _dl_err:
                    if _attempt == 0:
                        logger.warning(
                            "SentenceTransformer('%s') download failed: %s: %s — retrying...",
                            model_name, type(_dl_err).__name__, _dl_err,
                        )
                        continue
                    logger.warning(
                        "SentenceTransformer('%s') download failed (2 attempts): %s: %s — "
                        "semantic features disabled.",
                        model_name, type(_dl_err).__name__, _dl_err,
                    )
                    return None
            else:
                # Both attempts failed
                return None

            # Save permanently to the persistent directory so we never need
            # to download again.
            try:
                _model_dir.mkdir(parents=True, exist_ok=True)
                _embed_model.save(str(_model_dir))
                logger.info("SentenceTransformer saved to: %s", _model_dir)
            except Exception as save_err:
                logger.warning(
                    "Could not save model to %s: %s: %s",
                    _model_dir, type(save_err).__name__, save_err,
                )

            _embed_model_name = model_name
            # V18.20.4.12 (W-c17): the process-wide offline lock that used to
            # be set here (HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE = "1") is
            # REMOVED — the flags are now scoped to the offline from-disk
            # load only (see the ``_is_saved`` branch above).  Leaving them
            # set here silently forced all later HuggingFace network access
            # (e.g. downloading a different model) offline for the session.
            # V18.2.44 (Next Step #5): wrap + smoke-test the freshly-downloaded
            # model too (same protection as the from-disk path above).
            from core.llm.embedder_backend import SentenceTransformerBackend
            _wrapped = SentenceTransformerBackend(_embed_model)
            if not _wrapped.smoke_test():
                logger.warning(
                    "V18.2.44: SentenceTransformerBackend smoke-test FAILED "
                    "for freshly-downloaded '%s' (%s). The model loaded but "
                    "produces degenerate vectors — semantic similarity will "
                    "fall back to Jaccard.",
                    model_name, _wrapped._health_reason,
                )
            _embed_model = _wrapped
            return _embed_model
        except ImportError:
            logger.debug(
                "sentence-transformers not installed — embed model unavailable"
            )
            return None
        except Exception as exc:
            logger.warning(
                "Failed to load SentenceTransformer('%s'): %s: %s",
                model_name, type(exc).__name__, exc,
            )
            return None


def is_embedder_healthy() -> bool:
    """V18.2.37b: Check if the embedder backend is healthy.

    V18.2.35: TRIGGER LAZY LOAD FIRST — call get_embed_model() if not loaded.
    V18.2.37b: Set _FORCE_CPU_EMBEDDER flag when IQ2_XXS is active.
    The flag is checked by _resolve_embed_device() — no monkeypatch needed.

    Returns True if the embedder is available and healthy.
    Returns False if loading failed or the backend is marked unhealthy.
    """
    global _embed_model, _FORCE_CPU_EMBEDDER
    # V18.2.35: trigger the lazy load if the model hasn't been loaded yet.
    if _embed_model is None:
        # V18.2.37b: check if IQ2_XXS is active — if so, set the CPU flag
        # BEFORE calling get_embed_model(). _resolve_embed_device() will
        # check this flag and return "cpu", avoiding the VRAM conflict.
        # V18.3 (Phase 1.1): replaced inline regex with model_taxonomy.
        try:
            from core.llm.model_taxonomy import is_low_bit_quant
            from utils.settings import Settings
            _model_name = Settings().get("summarisation.model", "")
            if is_low_bit_quant(_model_name):
                _FORCE_CPU_EMBEDDER = True
                logger.info(
                    "V18.2.37b: forcing embedder to CPU (low-bit quant model active — "
                    "GPU VRAM is needed for the LLM, embedder runs on CPU ~1-3s/batch)"
                )
        except Exception:
            pass
        _embed_model = get_embed_model()
    if _embed_model is None:
        return False
    # OllamaEmbedBackend has a .healthy flag; SentenceTransformer doesn't
    healthy = getattr(_embed_model, "healthy", True)
    return bool(healthy)


def get_spacy_nlp(
    model_name: str = "en_core_web_sm",
    disable: list | None = None,
) -> Any | None:
    """Return a shared ``spacy.Language`` instance (lazy singleton, one per model).

    Loads on first call for a given model name, returns the cached instance
    on subsequent calls.  Returns ``None`` if spacy or the model isn't
    installed.

    Parameters
    ----------
    model_name:
        The spacy model name (e.g. ``"en_core_web_sm"``).
    disable:
        Optional list of pipeline components to disable (e.g.
        ``["parser", "tagger"]`` for tokeniser-only use).  Only applied
        on first load; subsequent calls get the same instance regardless
        of this argument.
    """
    cache_key = model_name
    if cache_key in _spacy_nlp_cache:
        return _spacy_nlp_cache[cache_key]
    with _lock:
        if cache_key in _spacy_nlp_cache:
            return _spacy_nlp_cache[cache_key]
        try:
            import spacy
            logger.debug("Loading spacy('%s', disable=%s) (one-time)",
                         model_name, disable)
            if disable:
                nlp = spacy.load(model_name, disable=disable)
            else:
                nlp = spacy.load(model_name)
            _spacy_nlp_cache[cache_key] = nlp
            logger.debug("spacy loaded: %s", model_name)
            return nlp
        except ImportError:
            logger.debug("spacy not installed — nlp unavailable")
            return None
        except Exception as exc:
            # spacy.load raises OSError if the model isn't installed
            logger.warning("Failed to load spacy('%s'): %s: %s",
                           model_name, type(exc).__name__, exc)
            return None


def reset_singletons() -> None:
    """Clear all cached models (for testing).

    After calling this, the next ``get_embed_model()`` / ``get_spacy_nlp()``
    call will re-load the model.  Used by tests that need to verify the
    lazy-loading behaviour.
    """
    global _embed_model, _embed_model_name
    with _lock:
        _embed_model = None
        _embed_model_name = None
        _spacy_nlp_cache.clear()


__all__ = [
    "get_embed_model",
    "get_spacy_nlp",
    "reset_singletons",
]
