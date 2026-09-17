"""V18.2.45 (Phase 0): Single source of truth for model classification.

Before this module, the heuristic for detecting "low-bit quant" models was
duplicated across 5 files with 4 slightly-different token lists:

    llm_provider.py   — ("iq2_xxs", "iq2_xs", "q2_k", "q2_")
    summarizer.py #1  — ("iq2_xxs", "iq2_xs", "iq1", "q2_k", "q2_")
    summarizer.py #2  — ("iq2_xxs", "iq2_xs", "iq2_s", "iq1", "q2_k", "q2_")
    model_singletons  — ("iq2_xxs", "iq2_xs", "iq1", "q2_k", "q2_", "q1_")
    prompt_manager    — ("iq2_xxs", "iq2_xs", "iq1", "q2_k", "q2_")

Adding a new quant (e.g. ``iq3``) required 5 edits; missing one = silent
misclassification.  This module replaces all of them with one canonical API.

**Phase 0 status:** this module is created but NOT YET WIRED into any call
site.  Phase 1 (item 1.1) replaces each inline ``any(q in m for q in (...))``
with ``is_low_bit_quant(model)``.  Until then, the functions here are pure
additions — zero risk to the gold-standard pipeline.

Design notes:
  - The token list is the **union** of all 5 sites (the most complete
    detection).  Sites that previously omitted ``iq1`` or ``q1_`` will gain
    that detection when wired in Phase 1 — this is strictly more correct (IQ1
    is even more quantized than IQ2 and should always be treated as low-bit).
  - ``is_iq2_s()`` is a separate predicate because the ``num_ctx`` cap logic
    in ``llm_provider._adaptive_context`` distinguishes IQ2_S (cap 26758)
    from Q2_K_XL (cap 16000) — both contain ``q2_`` but only IQ2_S has
    ``iq2_s`` without ``q2_k``.
  - Parameter-count extraction (``param_count_b``) replicates the regex
    ``r'(\\d+(?:\\.\\d+)?)\\s*[bB]\\b'`` used in ``llm_provider.py`` and
    ``summarizer.py``.

Usage::

    from core.llm.model_taxonomy import is_low_bit_quant, is_small_model

    if is_low_bit_quant(model_name):
        # use the lowbit consolidation prompt, skip sanitizer, etc.
    if is_small_model(model_name):
        # cap max_output at 8192, disable Academic Rigor
"""
from __future__ import annotations

import re

__all__ = [
    "LOW_BIT_TOKENS",
    "is_low_bit_quant",
    "is_iq2_s",
    "param_count_b",
    "is_small_model",
    "is_27b_plus",
    "recommended_ctx_cap",
]


# ── Token lists ────────────────────────────────────────────────────────────

# Union of all 9 inline token lists across the codebase (Phase 1 audit).
# Ordered longest-first so that ``iq2_xxs`` is checked before ``iq2_x`` —
# though ``any()`` with ``in`` is substring-based so order doesn't affect
# correctness, only documentation clarity.
#
# Phase 1.0: added ``iq2_m`` and ``iq0`` (from summarizer.py:401's list) so
# this is now the true union of every inline low-bit check in the codebase.
LOW_BIT_TOKENS: tuple[str, ...] = (
    "iq2_xxs",   # 1.9-bit
    "iq2_xs",    # 2.2-bit
    "iq2_s",     # 2.4-bit  (gold standard quant)
    "iq2_m",     # 2.2-bit medium  (Phase 1.0: from summarizer.py:401)
    "iq1",       # 1.0-bit
    "iq0",       # 0-bit   (Phase 1.0: from summarizer.py:401 — extreme low-bit)
    "q2_k",      # 2-bit K-quants (Q2_K, Q2_K_XL, Q2_K_S) — redundant with q2_ but explicit
    "q2_",       # generic 2-bit prefix (catches q2_k, q2_s, AND iq2_* via substring)
    "q1_",       # generic 1-bit prefix (catches q1_0, etc.)
)


# ── Predicates ─────────────────────────────────────────────────────────────

def is_low_bit_quant(model: str | None) -> bool:
    """True if the model name indicates a low-bit quantization.

    Detects: IQ2_XXS, IQ2_XS, IQ2_S, IQ1_*, Q2_K*, Q2_*, Q1_*.

    This is the canonical replacement for the 5 inline ``any(q in m for q
    in (...))`` heuristics.  Uses the **union** of all previous token lists,
    so it is strictly more complete than any individual site.

    >>> is_low_bit_quant("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest")
    True
    >>> is_low_bit_quant("Qwen3.8-27B-UD-Q2_K_XL:latest")
    True
    >>> is_low_bit_quant("Qwen3.8-27B-UD-IQ2_M:latest")
    True
    >>> is_low_bit_quant("Qwen3.8-27B-UD-IQ0:latest")
    True
    >>> is_low_bit_quant("Qwen3.8-27B-Q8_0:latest")
    False
    >>> is_low_bit_quant("Qwen3.8-9B-Q8:latest")
    False
    >>> is_low_bit_quant("")
    False
    >>> is_low_bit_quant(None)
    False
    """
    if not model:
        return False
    m = model.lower()
    return any(tok in m for tok in LOW_BIT_TOKENS)


def is_iq2_s(model: str | None) -> bool:
    """True if the model is specifically IQ2_S (not Q2_K).

    Used by the ``num_ctx`` cap logic: IQ2_S gets 26758 (1.59 GB headroom),
    Q2_K_XL gets 16000 (only 0.82 GB headroom at 26758 — too tight).

    Detection: contains ``iq2_s`` but NOT ``q2_k`` (so Q2_K_S, which contains
    both ``q2_k`` and ``q2_s``, is correctly classified as NOT IQ2_S).

    >>> is_iq2_s("Qwen3.8-27B-UD-IQ2_S:latest")
    True
    >>> is_iq2_s("Qwen3.8-27B-UD-Q2_K_XL:latest")
    False
    >>> is_iq2_s("Qwen3.8-27B-UD-Q2_K_S:latest")
    False
    """
    if not model:
        return False
    m = model.lower()
    return "iq2_s" in m and "q2_k" not in m


# ── Parameter-count extraction ─────────────────────────────────────────────

# Same regex as llm_provider.py / summarizer.py inline:
_PARAM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*[bB]\b')


def param_count_b(model: str | None) -> float:
    """Extract the parameter count in billions from a model name.

    Returns 0.0 if no ``<number>B`` pattern is found.

    >>> param_count_b("Qwen3.8-27B-UD-IQ2_S:latest")
    27.0
    >>> param_count_b("Qwen3.8-9B-Q8:latest")
    9.0
    >>> param_count_b("llama3:8b")
    8.0
    >>> param_count_b("unknown-model")
    0.0
    >>> param_count_b(None)
    0.0
    """
    if not model:
        return 0.0
    m = _PARAM_RE.search(model)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except (ValueError, IndexError):
        return 0.0


# ── Composite predicates ────────────────────────────────────────────────────

def is_small_model(model: str | None, threshold: float = 13.0) -> bool:
    """True if the model has < ``threshold`` billion parameters.

    V18.2.39: small models (< 13B) can't handle 16000-token output budgets —
    they run out of attention capacity and produce prompt-leakage / empty
    responses.  ``is_small_model`` gates the ``max_output=8192`` cap and the
    Academic-Rigor disable.

    The threshold defaults to 13.0 (V18.2.39) — 9B models are small, 14B+
    are not.  The check is ``0 < params < threshold`` so unknown-size models
    (param_count_b returns 0.0) are NOT classified as small (conservative —
    they get the full output budget, same as current behavior).

    >>> is_small_model("Qwen3.8-9B-Q8:latest")
    True
    >>> is_small_model("Qwen3.8-27B-UD-IQ2_S:latest")
    False
    >>> is_small_model("unknown-model")
    False
    >>> is_small_model("Qwen3.8-14B-Q8:latest")
    False
    """
    p = param_count_b(model)
    return 0 < p < threshold


def is_27b_plus(model: str | None) -> bool:
    """True if the model has ≥ 20 billion parameters.

    Used by the ``num_ctx`` cap logic: 27B+ models on ≤12 GB cards need a
    context cap (the KV cache is proportional to layer count × context, and
    27B models have 64 layers → 1.64 GB KV at 26758 context).

    The threshold is 20.0 (not 27.0) to also catch 32B and 70B models.

    >>> is_27b_plus("Qwen3.8-27B-UD-IQ2_S:latest")
    True
    >>> is_27b_plus("Qwen3.8-9B-Q8:latest")
    False
    >>> is_27b_plus("Qwen3.8-32B:latest")
    True
    """
    return param_count_b(model) >= 20.0


# ── Context-cap recommendation ──────────────────────────────────────────────

def recommended_ctx_cap(
    model: str | None,
    gpu_total_gb: float,
) -> int | None:
    """Return the recommended ``num_ctx`` cap, or ``None`` for no cap.

    Replicates the logic in ``llm_provider._adaptive_context`` (V18.2.43):

    - IQ2_S 27B on ≤ 12 GB  →  26758  (1.59 GB headroom)
    - Q2_K*  27B on ≤ 12 GB  →  16000  (0.82 GB headroom — 26758 too tight)
    - IQ2_XXS/XS 27B ≤ 12 GB →  16000  (conservative default)
    - Small models / big GPUs   →  None  (no cap)

    Returns ``None`` when no cap is needed (caller uses the full
    ``context_tokens``).

    >>> recommended_ctx_cap("Qwen3.8-27B-UD-IQ2_S:latest", 12.0)
    26758
    >>> recommended_ctx_cap("Qwen3.8-27B-UD-Q2_K_XL:latest", 12.0)
    16000
    >>> recommended_ctx_cap("Qwen3.8-27B-UD-IQ2_XXS:latest", 12.0)
    16000
    >>> recommended_ctx_cap("Qwen3.8-27B-UD-IQ2_S:latest", 24.0)
    >>> recommended_ctx_cap("Qwen3.8-9B-Q8:latest", 12.0)
    >>> recommended_ctx_cap("Qwen3.8-27B-Q8:latest", 12.0)
    """
    if not model:
        return None
    if not is_low_bit_quant(model):
        return None
    if not is_27b_plus(model):
        return None
    if gpu_total_gb > 12.0:
        return None

    # IQ2_S has more VRAM headroom than Q2_K_XL (8.37 GB vs 9.80 GB file size).
    if is_iq2_s(model):
        return 26758
    # Q2_K_XL, IQ2_XXS, IQ2_XS — conservative 16000 cap.
    return 16000
