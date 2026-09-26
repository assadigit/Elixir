"""V10.13.0 (A5): Pre-flight dependency check.

Verifies that all required optional dependencies are importable BEFORE
starting a conversion.  A conversion can take 90+ minutes — failing 7
minutes in because ``tiktoken`` isn't installed is a terrible UX.

This module checks:
  - Core deps: pypdf, pdf2image, markitdown
  - Token deps: tiktoken
  - LLM deps: requests (for Ollama)
  - Optional deps: torch, transformers, rapidfuzz
  - Feature-specific deps: camelot (tables), reportlab (packets PDF)
  - sentence-transformers — ONLY when the active embedder is the HF/local
    backend (V18.20.3.3 crash fix #1; see ``_sentence_transformers_needed``)

Usage (from converter.convert())::

    from core.system.preflight_check import run_preflight_check
    missing = run_preflight_check(request, log_callback=self._log)
    if missing:
        return ConversionResult(success=False, error_msg=missing)

The function returns ``None`` if all deps are OK, or an error string
listing the missing deps + install instructions.

V18.20.3.3 (crash fixes #1/#2/#3) — the startup-crash hardening:

  #1  ``sentence_transformers`` is no longer imported whenever keypoints
      are enabled.  The requirement is resolved from the ACTIVE embedder
      (``settings.embedding.model`` + ``is_ollama_embed_model()``): the
      default ``nomic-embed-text`` embedder runs via Ollama's HTTP API and
      needs NO Python package, so rigs like the RTX 3060 (Ollama embedder
      since V18.15.1) skip the heaviest import in the whole startup path
      (~15-20 s — it pulls transformers + tokenizers + torch interplay)
      entirely.  That import was pure dead weight sitting exactly where
      the V18.20.3 process died.

  #2  Every import now emits a ``🔍 importing 'X'…`` line BEFORE it starts
      (flushed to the .conversion.log.md immediately) and an elapsed-time
      line after — so a process death inside the import window names the
      culprit module in the file instead of vanishing silently (the
      V18.20.3 crash left exactly one log line and no evidence).

  #3  ``_is_importable`` catches ``BaseException``: a ``SystemExit`` (or
      any non-``Exception`` escape) raised by a dependency's import code
      is treated as "not installable" + a LOUD error, instead of silently
      killing the conversion worker thread.
"""

from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# ── V18.20.3.3 (crash fix #1): embedder-aware requirement resolution ──────


def _resolve_embed_model_name() -> str:
    """Resolve the active embedding model exactly like ``get_embed_model()``.

    Single source of truth: ``settings.embedding.model`` (default
    ``nomic-embed-text`` — the V18.15.1 default that runs via Ollama and
    needs no ``sentence_transformers`` package).  Falls back to the same
    default ``get_embed_model()`` uses when the settings layer is
    unavailable.
    """
    try:
        from utils.settings import Settings

        return str(Settings().get("embedding.model", "nomic-embed-text") or "nomic-embed-text")
    except Exception:
        return "nomic-embed-text"


def _sentence_transformers_needed(request: Any) -> tuple[bool, str]:
    """Does THIS conversion actually need the sentence-transformers package?

    V18.20.3.3 (crash fix #1): previously the requirement was
    ``include_keypoints`` alone — so pre-flight imported
    ``sentence_transformers`` UNCONDITIONALLY whenever keypoints were on,
    even when the embedder was ``nomic-embed-text`` via Ollama (the
    default since V18.15.1), which needs NO Python package at all.  That
    made the heaviest import in the startup path (~15-20 s) pure dead
    weight on Ollama-embedder rigs — sitting exactly where the V18.20.3
    process died silently (the 21 s window between "Starting conversion…"
    and "Pre-flight dependency check passed").

    Resolution order (mirrors ``get_embed_model()`` in
    ``core/llm/model_singletons.py``):
      1. ``include_keypoints`` off → not needed (nothing embeds).
      2. ``embedding.enabled`` off → not needed (semantic path runs its
         Jaccard fallback by design — no embedder is ever constructed).
      3. ``embedding.model`` looks like an Ollama/GGUF model
         (``is_ollama_embed_model``) → not needed (Ollama HTTP API).
      4. Otherwise (HF/local name like ``BAAI/bge-small-en-v1.5`` or
         ``all-MiniLM-L6-v2``) → needed.

    Returns ``(needed, reason)`` — ``reason`` is logged so the conversion
    log always shows WHY the package was required or skipped.
    """
    if not getattr(request, "include_keypoints", False):
        return False, "keypoints disabled for this conversion"
    model_name = "nomic-embed-text"
    try:
        from utils.settings import Settings

        _s = Settings()
        if not _s.get("embedding.enabled", True):
            return False, "embedder disabled (embedding.enabled=false → Jaccard fallback)"
        model_name = str(_s.get("embedding.model", "nomic-embed-text") or "nomic-embed-text")
    except Exception:
        model_name = "nomic-embed-text"  # same fallback as get_embed_model()
    try:
        from core.llm.embedder_backend import is_ollama_embed_model

        if is_ollama_embed_model(model_name):
            return False, f"embedder '{model_name}' runs via Ollama (no Python package needed)"
    except Exception as exc:
        # Can't load the backend selector — be conservative (old behaviour):
        # keep requiring the package rather than under-requiring it.
        return True, (
            f"embedder backend check failed ({type(exc).__name__}: {exc}) "
            f"— assuming HF/local model '{model_name}'"
        )
    return True, f"embedder '{model_name}' is HF/local (sentence-transformers format)"


# ── Dependency registry ────────────────────────────────────────────────────
# Each entry: (import_name, display_name, pip_install, when_required)
# `when_required` is a function(request) -> bool that determines if the dep
# is needed for this specific conversion.
_REQUIRED_DEPS: list[tuple] = [
    # Core — always needed
    ("pypdf", "pypdf (PDF reading)", "pip install pypdf", lambda r: True),
    ("pdf2image", "pdf2image (cover screenshots)", "pip install pdf2image", lambda r: True),
    # Token counting — needed for summarization
    (
        "tiktoken",
        "tiktoken (token counting)",
        "pip install tiktoken",
        lambda r: getattr(r, "generate_summaries", False),
    ),
    # OCR — needed when use_llm_ocr is True
    # markitdown is imported at module level by core.pdf — always needed
    ("markitdown", "markitdown (text extraction)", "pip install markitdown", lambda r: True),
    # Dedup — needed for keypoints
    (
        "rapidfuzz",
        "rapidfuzz (fuzzy dedup)",
        "pip install rapidfuzz",
        lambda r: getattr(r, "include_keypoints", False),
    ),
    # Tables — needed when extract_tables is True
    (
        "camelot",
        "camelot (table extraction)",
        "pip install camelot-py[cv]",
        lambda r: getattr(r, "extract_tables", False),
    ),
    # Math — needed when extract_math is True
    (
        "pix2tex",
        "pix2tex (math extraction)",
        "pip install pix2tex",
        lambda r: getattr(r, "extract_math", False),
    ),
    # Layout — needed when layout_analysis is True
    (
        "pdfplumber",
        "pdfplumber (layout analysis)",
        "pip install pdfplumber",
        lambda r: getattr(r, "layout_analysis", False),
    ),
    # Embedding dedup — needed for keypoints, but ONLY when the ACTIVE
    # embedder is the sentence-transformers (HF/local) backend.
    # V18.20.3.3 (crash fix #1): resolved from settings.embedding.model +
    # is_ollama_embed_model() — the Ollama embedder (nomic-embed-text,
    # default since V18.15.1) needs NO Python package, so rigs using it
    # skip the ~15-20 s sentence_transformers import entirely.
    (
        "sentence_transformers",
        "sentence-transformers (embedding dedup)",
        "pip install sentence-transformers",
        lambda r: _sentence_transformers_needed(r)[0],
    ),
]

# Deps that are ALWAYS optional (never block conversion, just log a warning)
_OPTIONAL_DEPS: list[tuple] = [
    ("torch", "PyTorch (GPU/VRAM detection)", "pip install torch"),
    ("transformers", "transformers (NLLB translation)", "pip install transformers"),
    ("langextract", "langextract (source grounding)", "pip install langextract"),
]


def run_preflight_check(
    request: Any,
    log_callback: Callable[[str, str], None] | None = None,
) -> str | None:
    """Run pre-flight dependency check.

    Args:
        request: the ConversionRequest (used to determine which deps are needed)
        log_callback: ``fn(message, level)`` for progress logging

    Returns:
        ``None`` if all required deps are available.
        An error string if any required deps are missing (with install instructions).
    """
    log = log_callback or (lambda msg, level="INFO": None)

    missing_required: list[str] = []
    missing_optional: list[str] = []

    # Check required deps
    for import_name, display_name, pip_install, when_required in _REQUIRED_DEPS:
        if not when_required(request):
            # V18.20.3.3 (crash fix #1): skipped deps get a trace line too,
            # so the log always shows WHY a package wasn't imported.  The
            # sentence-transformers skip is logged at INFO because it is
            # the crash-fix-#1 behaviour change (Ollama-embedder rigs no
            # longer pay the ~15-20 s import at all).
            if import_name == "sentence_transformers":
                _need, _reason = _sentence_transformers_needed(request)
                log(f"  ⏭️ sentence-transformers skipped — {_reason}", "INFO")
            else:
                log(f"  ⏭️ '{import_name}' not needed for this conversion", "DEBUG")
            continue  # not needed for this conversion
        if not _is_importable(import_name, log=log):
            missing_required.append(f"  • {display_name} — {pip_install}")

    # Check optional deps (log warning, don't block).
    # V0.5.3 (FIX-P1-3a, post-AUDIT-V0.5.2): use the INSTANT ``_is_installed``
    # (find_spec) for optional deps instead of the eager ``_is_importable``
    # (import_module). The eager import was the root cause of the 4-minute
    # init reported on the RTX 3060 rig: ``transformers`` alone took 15.8s
    # (V0.5.0) → 20.5s (V0.5.1) → 36s (V0.5.2 run) per conversion, even
    # though elixir does NOT directly ``import transformers`` (only the
    # optional NLLB-translation feature uses it). find_spec checks that the
    # module is INSTALLED (findable on sys.path) without executing its
    # import-time code — instant. Optional deps only log a warning (don't
    # block), so we don't need to catch import-time errors here (any error
    # will surface at use time when the feature is actually invoked).
    for import_name, display_name, pip_install in _OPTIONAL_DEPS:
        if not _is_installed(import_name, log=log):
            missing_optional.append(f"  • {display_name} — {pip_install}")

    # Log optional missing deps
    if missing_optional:
        log(
            "  ℹ️ Optional dependencies not installed (some features may be limited):\n"
            + "\n".join(missing_optional),
            "DEBUG",
        )

    # Block on required missing deps
    if missing_required:
        msg = (
            "Missing required dependencies for this conversion:\n"
            + "\n".join(missing_required)
            + "\n\nInstall them with pip, then re-run the conversion."
        )
        log(f"❌ Pre-flight check FAILED: {len(missing_required)} missing deps", "ERROR")
        return msg

    log("  ✅ Pre-flight dependency check passed", "DEBUG")
    return None


def check_disk_space(
    output_dir: Any,
    estimated_mb: float = 500.0,
    min_free_gb: float = 2.0,
    log: Callable[[str, str], None] | None = None,
) -> str | None:
    """V10.34.0 (Sprint 6.8): Check that the output directory has enough free disk space.

    Estimates the conversion output size (default 500 MB for a typical
    20-chapter book with summaries + keypoints + a few outputs) and warns
    if the free space on the target drive is below ``min_free_gb``.

    Returns ``None`` if OK, or a warning string if space is low.
    Never blocks the conversion (just warns) — the user may know better
    than our estimate.
    """
    if log is None:

        def _noop_log(msg: str, level: str = "DEBUG") -> None:
            pass

        log = _noop_log
    try:
        import shutil

        output_path = Path(str(output_dir))
        # Create the dir if it doesn't exist (so we can check its drive)
        output_path.mkdir(parents=True, exist_ok=True)
        total, used, free = shutil.disk_usage(output_path)
        free_gb = free / (1024**3)

        if free_gb < min_free_gb:
            msg = (
                f"⚠️ Low disk space: only {free_gb:.1f} GB free on {output_path.anchor} "
                f"(recommended: ≥{min_free_gb:.0f} GB). "
                f"Estimated output size: ~{estimated_mb:.0f} MB. "
                f"The conversion may fail partway through if disk fills up."
            )
            log(msg, "WARNING")
            return msg
        else:
            log(
                f"  💾 Disk space OK: {free_gb:.1f} GB free "
                f"(estimated output ~{estimated_mb:.0f} MB)",
                "DEBUG",
            )
        return None
    except Exception as exc:
        log(f"  ℹ️ Disk space check skipped ({exc})", "DEBUG")
        return None


from pathlib import Path  # noqa: E402 (moved here to avoid top-level import order issues)


def _is_importable(
    module_name: str,
    log: Callable[[str, str], None] | None = None,
) -> bool:
    """Check if a module can be imported.

    V18.20.3.3 (crash fixes #2 + #3):

    #2 — Per-import log lines.  A ``🔍 importing 'X'…`` line is emitted
    BEFORE the import starts (the ConversionLogger flushes every line to
    the .conversion.log.md immediately) and an elapsed-time line after.
    If the process dies inside the import window — a native DLL crash, a
    ``SystemExit`` raised by the dependency, an OOM kill — the LAST line
    in the file names the culprit module instead of the log just stopping
    dead with no evidence (the exact V18.20.3 failure signature).

    #3 — ``BaseException`` is caught.  Previously only ``ImportError``
    and ``Exception`` were handled: a ``SystemExit`` (or any other
    ``BaseException`` that is not an ``Exception``) escaping a
    dependency's import code bypassed BOTH handlers and silently killed
    the conversion worker thread — no dialog, no log line, and the wizard
    stayed stuck on "Starting conversion…" forever.  Now it is treated
    as "not installable" with a LOUD error and surfaces as a normal
    pre-flight failure instead.
    """
    _log = log or (lambda msg, level="DEBUG": None)
    _log(f"  🔍 importing '{module_name}'…", "DEBUG")
    _t0 = time.perf_counter()
    try:
        importlib.import_module(module_name)
        _dt = time.perf_counter() - _t0
        _log(f"  ✅ '{module_name}' ok ({_dt:.1f}s)", "DEBUG")
        return True
    except ImportError:
        _log(f"  ❌ '{module_name}' not installed", "DEBUG")
        return False
    except Exception as _e:
        # Some modules have import-time errors (e.g. torch without CUDA)
        # — treat as importable (the error will surface at use time).
        # V18.20.3.3: now VISIBLE (was silently swallowed before).
        _dt = time.perf_counter() - _t0
        _log(
            f"  ⚠️ '{module_name}' import raised {type(_e).__name__}: {_e} "
            f"(after {_dt:.1f}s) — treating as installable, error will "
            f"surface at use time",
            "WARNING",
        )
        return True
    except BaseException as _e:
        # SystemExit / KeyboardInterrupt / GeneratorExit / anything else
        # that is not an Exception.  These used to escape BOTH handlers
        # above and silently kill the worker thread (crash fix #3).
        _dt = time.perf_counter() - _t0
        _log(
            f"❌ import of '{module_name}' raised {type(_e).__name__}: {_e} "
            f"(after {_dt:.1f}s) — treating as NOT installable",
            "ERROR",
        )
        return False


def _is_installed(
    module_name: str,
    log: Callable[[str, str], None] | None = None,
) -> bool:
    """Check if a module is INSTALLED (findable on ``sys.path``).

    V0.5.3 (FIX-P1-3a, post-AUDIT-V0.5.2): an instant alternative to
    ``_is_importable`` for OPTIONAL deps. Uses
    ``importlib.util.find_spec`` which returns a ``ModuleSpec`` if the
    module is findable, ``None`` otherwise — WITHOUT executing the
    module's import-time code.

    Why this matters: ``_is_importable`` does a full
    ``importlib.import_module`` which executes the module's top-level
    code. For ``transformers`` that top-level code pulls in the entire
    HF ecosystem (tokenizers, torch interplay, etc.) and took 15.8s
    (V0.5.0) → 20.5s (V0.5.1) → 36s (V0.5.2 run) per conversion on the
    RTX 3060 rig — even though elixir does NOT directly use
    ``transformers`` (only the optional NLLB-translation feature does).
    For OPTIONAL deps (which only log a warning, never block the
    conversion), we don't need to verify the module can be IMPORTED
    without error — we just need to know it's installed. Any import-time
    error will surface at use time when the feature is actually invoked.

    Trade-off: ``find_spec`` does NOT catch the case where a module is
    installed but broken (e.g. ``torch`` without CUDA raises at import).
    For REQUIRED deps we keep ``_is_importable`` (catches import-time
    errors early, before a 90-minute conversion). For OPTIONAL deps the
    trade-off is correct: instant check, deferred errors.

    Returns ``True`` if the module is findable, ``False`` otherwise.
    """
    _log = log or (lambda msg, level="DEBUG": None)
    try:
        import importlib.util

        spec = importlib.util.find_spec(module_name)
        if spec is None:
            _log(f"  ❌ '{module_name}' not installed", "DEBUG")
            return False
        _log(f"  ✅ '{module_name}' installed", "DEBUG")
        return True
    except Exception as _e:
        # find_spec can raise ModuleNotFoundError for parent packages of
        # a submodule (e.g. find_spec('foo.bar') when 'foo' is absent).
        # Treat any exception as "not installed" — consistent with the
        # _is_importable ImportError branch.
        _log(f"  ❌ '{module_name}' not installed ({type(_e).__name__})", "DEBUG")
        return False


def get_dependency_status() -> dict[str, bool]:
    """Get the status of all known dependencies.

    Returns a dict of {module_name: is_available} for all registered deps.
    Useful for the Dependencies Dashboard UI.

    V0.5.3 (FIX-P1-3a): optional deps now use the instant ``_is_installed``
    (find_spec) — the Dashboard UI shouldn't pay the 15-36s ``transformers``
    import cost just to display a status row. Required deps still use
    ``_is_importable`` (catches import-time errors).
    """
    status = {}
    for import_name, _, _, _ in _REQUIRED_DEPS:
        status[import_name] = _is_importable(import_name)
    for import_name, _, _ in _OPTIONAL_DEPS:
        status[import_name] = _is_installed(import_name)
    return status
