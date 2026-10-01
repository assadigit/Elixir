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
    "VISION_MODEL_KEYWORDS",  # V0.6.7 (review-loop B4): the vision-model SSOT
    "LEGACY_DEFAULT_MODEL",  # V18.20.4.11 (P2): legacy "gemma3:12b" sentinel
    "DEFAULT_FALLBACK_OCR_MODEL",  # V18.20.4.11 (P2): "qwen3-vl:8b" request-side OCR default
    "RIG_FALLBACK_MODEL",  # V18.20.4.12 (W-a10): rig-tuned qwythos fallback tag
    "KNOWN_BAD_MODEL_ALIASES",  # V18.20.4.12 (W-a10): names that 404 — never default to these
    "is_low_bit_quant",
    "is_iq2_s",
    "is_vision_model",  # V0.6.7 (review-loop B4)
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
    "iq2_xxs",  # 1.9-bit
    "iq2_xs",  # 2.2-bit
    "iq2_s",  # 2.4-bit  (gold standard quant)
    "iq2_m",  # 2.2-bit medium  (Phase 1.0: from summarizer.py:401)
    "iq1",  # 1.0-bit
    "iq0",  # 0-bit   (Phase 1.0: from summarizer.py:401 — extreme low-bit)
    "q2_k",  # 2-bit K-quants (Q2_K, Q2_K_XL, Q2_K_S) — redundant with q2_ but explicit
    "q2_",  # generic 2-bit prefix (catches q2_k, q2_s, AND iq2_* via substring)
    "q1_",  # generic 1-bit prefix (catches q1_0, etc.)
)


# ── Vision-model classification keywords (V0.6.7 / review-loop B4) ─────────
#
# Before V0.6.7 the vision-model keyword heuristic was copy-pasted across
# 5 call sites in 3 DRIFTED variants:
#
#   utils/dependencies.py:85-93 + 137 (×2) —
#       vl, vision, deepseek-ocr, llava, bakllava, ocr, olmo
#   ui_qt/settings/sections/helpers.py:26 — same 7 (the badge helper)
#   ui_qt/views/about_system_dialog.py:225 — same 7 (the About dialog)
#   core/llm/llamacpp_provider.py:468-480 (the vision-attempt gate) —
#       vision, vl, vlm, mmproj, multimodal, llava, bakllava, qwen-vl,
#       gemma-vl, instruct-vision, bonsai
#   ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py:317-332 —
#       ocr, vision, vl, llava, minicpm, moondream, bakllava, llama-vision,
#       qwen-vl, internvl, cogvlm, fuyu, kosmos, florence
#
# The drift had a user-visible symptom: ``minicpm-v`` was listed in the OCR
# dialog (variant C) but classified TEXT by dependencies.py (variant A) —
# the exact misclassification this union fixes.
#
# This tuple is the UNION of all three variants (same policy as
# LOW_BIT_TOKENS: the most complete detection). Per-site behavior deltas
# when wiring to ``is_vision_model``:
#   - dependencies/badge/About (variant A sites) GAIN: mmproj, multimodal,
#     bonsai, minicpm, moondream, fuyu, kosmos, florence (+ the
#     substring-redundant vlm/qwen-vl/gemma-vl/instruct-vision/llama-vision/
#     internvl/cogvlm);
#   - the OCR dialog (variant C) GAINS: olmo, mmproj, multimodal, bonsai;
#   - the llamacpp gate (variant B) GAINS: ocr, deepseek-ocr, olmo, minicpm,
#     moondream, fuyu, kosmos, florence — vision families it previously
#     missed (a minicpm-v on llama.cpp silently degraded to Tesseract).
#
# CAVEAT (documented, kept for provenance): ``olmo`` matches text-only
# OLMo-family tags too. It was in variant A for years (dependencies/
# About/badge all classify olmo:7b as vision today); at the llamacpp gate
# a false positive costs one failed image attempt per page before the
# Qwen/Tesseract fall-through (core/ocr/service.py never treats a vision
# failure as fatal). Removing it would be a behavior change in the other
# direction and needs rig evidence — left in, flagged here.
#
# Substring-redundant entries (vl ⊂ vlm/qwen-vl/gemma-vl/internvl/cogvlm,
# vision ⊂ instruct-vision/llama-vision, ocr ⊂ deepseek-ocr) are kept for
# provenance, like LOW_BIT_TOKENS keeps ``q2_k`` alongside ``q2_``.
VISION_MODEL_KEYWORDS: tuple[str, ...] = (
    # — variant A (dependencies ×2, badge helper, About dialog) —
    "vl",
    "vision",
    "deepseek-ocr",
    "llava",
    "bakllava",
    "ocr",
    "olmo",
    # — variant B (the llamacpp vision-attempt gate) —
    "vlm",
    "mmproj",
    "multimodal",
    "qwen-vl",
    "gemma-vl",
    "instruct-vision",
    "bonsai",
    # — variant C (the OCR service dialog) —
    "minicpm",
    "moondream",
    "llama-vision",
    "internvl",
    "cogvlm",
    "fuyu",
    "kosmos",
    "florence",
)


# ── Legacy default-model sentinels (V18.20.4.11 / P2 / W-a7 partial) ────────
#
# Single source of truth for the legacy default-model string literals that
# were previously duplicated across the codebase (core/models/models.py ×4
# dataclass fields, core/summarisation/summarizer.py:614,
# core/tts/normalizer.py:405,
# core/pipeline/conversion/postprocess.py:442; V0.6.14: the
# core/summarisation/fast_llm.py site is retired with the single-model
# order). This is DE-DUPLICATION ONLY — every wired site keeps its exact
# value (zero behavior change).
#
# NOTE: ``LEGACY_DEFAULT_MODEL`` is a LEGACY SENTINEL, never a
# recommendation. It means "no explicit model configured" (V0.6.14: the
# old fast_llm.py consumer is retired with the single-model order):
#   - core/tts/normalizer.py treats it as a known-bad default and
#     auto-discovers a model from the Ollama daemon.
# Do NOT use it as a default for new features.
LEGACY_DEFAULT_MODEL: str = "gemma3:12b"

# ``ConversionRequest`` dataclass default for the OCR model fields
# (core/models/models.py primary_ocr_model / fallback_ocr_model) and the
# figure-text-extraction request fallback
# (core/pipeline/conversion/postprocess.py:442).
#
# KNOWN MISMATCH (flagged, deliberately NOT unified here): the OCR SERVICE
# defaults in utils/settings.py ("ocr.primary_model" /
# "ocr.fallback_model") are OlmOCR-2-7B variants while the REQUEST-side
# default is qwen3-vl:8b — unifying the VALUES is a behavior change that
# requires user sign-off and is out of scope for this literal cleanup.
DEFAULT_FALLBACK_OCR_MODEL: str = "qwen3-vl:8b"


# ── Rig-tuned fallback model + known-bad aliases (V18.20.4.12 / W-a10) ──────
#
# The user's rig-tuned fallback model (V13.45.5 user request: "before going
# to fallback, lets try qwythos model"). The CAPITALIZED ``-empero-v3`` form
# is the tag actually installed in the user's Ollama daemon (Ollama tags are
# case-sensitive). Used by:
#   - core/grounding/claim_extractor.py — the Pass-1 zero-extraction retry
#     (behavior byte-identical; previously an inline literal);
#   - the service dialogs + podcast maker — as the UI default when settings
#     are empty and Ollama is unreachable (V18.20.4.12: previously they
#     defaulted to the NON-empero variant below, which 404s — genuine bug).
# NOTE: this is a RIG-SPECIFIC personal model, not a recommendation for
# other installs — dialogs overwrite it with the live /api/tags list as
# soon as Ollama answers.
RIG_FALLBACK_MODEL: str = "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest"

# Model names that 404 on the rig and must NEVER be used as a default:
#   - the non-empero variant (wrong tag — utils/settings.py:989-990
#     documents it as "the model that doesn't exist in Ollama");
#   - the lowercase empero form (right tag, wrong case — Ollama tags are
#     case-sensitive; this was packets/generator.py's pre-V18.20.4.12
#     default and 404ed on every install).
# settings migrations and dialog defaults must never resolve to these;
# the tuple exists so future code can guard with
# ``model in KNOWN_BAD_MODEL_ALIASES``. utils/settings.py's
# model_temperatures KEYS deliberately keep listing them (config DATA for
# users who genuinely have those tags — untouched by W-a10).
KNOWN_BAD_MODEL_ALIASES: tuple[str, ...] = (
    "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest",
    "qwythos-9b-claude-mythos-5-1m-q4_k_m-empero-v3:latest",
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


def is_vision_model(model: str | None) -> bool:
    """True if the model name indicates a vision-capable family.

    V0.6.7 (review-loop B4): the canonical replacement for the 5 copy-pasted
    keyword heuristics (utils/dependencies ×2, the settings badge helper, the
    About dialog, the llamacpp vision gate, the OCR dialog). Uses the UNION of
    the 3 drifted variants — strictly more complete than any individual site
    (same policy as :func:`is_low_bit_quant`). See ``VISION_MODEL_KEYWORDS``
    for the per-site deltas and the ``olmo`` caveat.

    >>> is_vision_model("minicpm-v")   # the drift bug: was TEXT in dependencies
    True
    >>> is_vision_model("qwen2.5-vl:7b")
    True
    >>> is_vision_model("moondream2")
    True
    >>> is_vision_model("llama3.1:8b")
    False
    >>> is_vision_model("gemma3:12b")
    False
    >>> is_vision_model("")
    False
    >>> is_vision_model(None)
    False
    """
    if not model:
        return False
    m = model.lower()
    return any(kw in m for kw in VISION_MODEL_KEYWORDS)


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
_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")


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
