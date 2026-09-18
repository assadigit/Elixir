"""V7.1.0 S3: VRAM budget calculator.

V13.26.0: Complete rewrite with quantization + KV cache accounting.
Previously used name-substring matching with magic numbers — couldn't
distinguish Q4 from Q5 from Q8, ignored context window entirely. For
Gemma 4 12B Q5_K_XL at 32k context, it estimated 6.5 GB; real usage is
~10.6 GB. This rewrite fixes that.

Estimates VRAM usage based on:
1. **Model weights** — parameter count × quantization multiplier
   (parsed from model name: Q4_K_M, Q5_K_XL, Q8_0, F16, etc.)
2. **KV cache** — context window × per-token KV cache size
   (estimated from parameter count, accounts for GQA)
3. **Compute overhead** — ~0.5 GB for Ollama/llama.cpp compute buffers

Uses known VRAM estimates for common model sizes:
  - 7B Q4 models: ~5-6.5 GB total (weights + 8k KV cache)
  - 9B Q4 models: ~5-6.5 GB total
  - 12B Q5_K_XL at 32k: ~10.6 GB total (weights 8.6 + KV 1.8 + overhead 0.5)
  - 4B Q5 models: ~2.8 GB total
  - 600M NMT models: ~2.5 GB total
  - TTS engines: ~0.5-2 GB (NeuTTS) or ~0.5 GB (Kokoro/Piper)

The calculator checks:
  1. Which models will be loaded simultaneously
  2. Their estimated VRAM usage (weights + KV cache)
  3. Whether they fit in the available VRAM
  4. Recommends max_workers reduction if tight
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ModelVRAMEstimate:
    """VRAM estimate for a single model."""
    name: str
    role: str  # "OCR", "Summarization", "Translation", "Judge", "Harakat", "TTS"
    estimated_vram_gb: float
    loaded_simultaneously: bool = True


# ── Quantization multipliers (bytes per parameter) ──────────────────────────
# Based on GGUF format specifications. These are approximate but accurate
# enough for VRAM budgeting.
#
# V18.1 (audit): Added IQ (importance-matrix) quants — IQ2_M, IQ3, IQ4_XS.
# These are sub-2-bit / sub-3-bit quants used by Unsloth's 27B/32B releases.
# Without these, the calculator fell back to the Q4_K_M multiplier (0.58),
# overestimating a 27B IQ2 model at ~20 GB when the real footprint is ~7 GB.
_QUANT_MULTIPLIERS: dict[str, float] = {
    # ── IQ (importance-matrix) quants — sub-2-bit to 4-bit ──
    "iq2_xxs": 0.21,
    "iq2_xs":  0.22,
    "iq2_s":   0.23,
    "iq2_m":   0.25,   # Unsloth Qwen3.8-27B-UD-IQ2_M uses this
    "iq3_xxs": 0.30,
    "iq3_xs":  0.31,
    "iq3_s":   0.32,
    "iq3_m":   0.33,
    "iq4_xs":  0.40,
    "iq4_nl":  0.45,
    # ── V0.04: ternary (1.58-bit / BitNet-style) weights ──
    # Ternary packs weights at ~1.58 bits ≈ 0.20 raw bytes/param; with
    # scales/zero-points and f16 embeddings the effective GGUF footprint
    # of e.g. a 27B ternary lands ≈ 8 GB → ≈ 0.31 bytes/param. Without
    # this class the calculator fell back to the Q4_K_M multiplier (0.58),
    # estimating a 27B ternary at ~18 GB — a bogus "overbudget" verdict
    # for a model that actually fits a 12 GB card.
    "ternary": 0.31,
    "tn23":    0.31,   # common ternary tag suffix (e.g. …-tn23.gguf)
    # ── Standard K-quants ──
    "q4_0": 0.55,
    "q4_1": 0.58,
    "q4_k_s": 0.56,
    "q4_k_m": 0.58,
    "q5_0": 0.61,
    "q5_1": 0.63,
    "q5_k_s": 0.66,
    "q5_k_m": 0.68,
    "q5_k_xl": 0.72,  # Slightly larger than Q5_K_M
    "q6_k": 0.80,
    "q8_0": 1.00,
    "f16": 2.00,
    "f32": 4.00,
}

# Default quantization if none detected in model name
_DEFAULT_QUANT_MULTIPLIER = 0.58  # assume Q4_K_M (most common)

# Compute overhead for Ollama/llama.cpp (GB) — compute buffers, graph, etc.
_COMPUTE_OVERHEAD_GB = 0.5

# KV cache factor: per-token KV cache ≈ param_count * this factor * (ctx/32768)
# Based on typical architectures with GQA. For 12B at 32k: 12 * 0.15 * 1.0 = 1.8 GB
_KV_CACHE_FACTOR = 0.15


def _parse_param_count(model_name: str) -> float | None:
    """Parse parameter count (in billions) from model name.

    Handles: 12B, 12b, 9B, 7B, 4B, 3B, 1.3B, 1B, 600M, 1.5B, etc.
    Returns None if no parameter count found.
    """
    if not model_name:
        return None
    low = model_name.lower()

    # Match patterns like "12b", "9b", "1.3b", "600m", "1.5b"
    m = re.search(r'(\d+\.?\d*)\s*([bm])', low)
    if m:
        count = float(m.group(1))
        unit = m.group(2)
        if unit == 'b':
            return count  # already in billions
        elif unit == 'm':
            return count / 1000.0  # convert millions to billions
    return None


def _parse_quantization(model_name: str) -> tuple[str, float]:
    """Parse quantization tag from model name.

    Returns (quant_name, multiplier) where multiplier is bytes per parameter.
    Falls back to ("unknown", _DEFAULT_QUANT_MULTIPLIER) if not found.
    """
    if not model_name:
        return "unknown", _DEFAULT_QUANT_MULTIPLIER
    low = model_name.lower()

    # Check for explicit quantization tags (order matters — check longer/more-specific first).
    # V18.1: IQ quants checked first (they're longer than their Q counterparts).
    # V0.04: ternary FIRST — "Ternary-Bonsai-2-27B…" must not fall through
    # to the Q4_K_M default (see the _QUANT_MULTIPLIERS note above).
    for tag in ["ternary", "tn23",
                "iq2_xxs", "iq2_xs", "iq2_s", "iq2_m",
                "iq3_xxs", "iq3_xs", "iq3_s", "iq3_m",
                "iq4_xs", "iq4_nl",
                "q5_k_xl", "q5_k_m", "q5_k_s", "q4_k_m", "q4_k_s",
                "q6_k", "q8_0", "q5_0", "q5_1", "q4_0", "q4_1", "f16", "f32"]:
        if tag in low:
            return tag, _QUANT_MULTIPLIERS[tag]

    # Check for "q4" / "q5" / "q8" / "iq2" / "iq3" / "iq4" without subtype
    if re.search(r'\biq2\b', low):
        return "iq2", _QUANT_MULTIPLIERS["iq2_m"]
    if re.search(r'\biq3\b', low):
        return "iq3", _QUANT_MULTIPLIERS["iq3_m"]
    if re.search(r'\biq4\b', low):
        return "iq4", _QUANT_MULTIPLIERS["iq4_xs"]
    if re.search(r'\bq4\b', low):
        return "q4", _QUANT_MULTIPLIERS["q4_k_m"]
    if re.search(r'\bq5\b', low):
        return "q5", _QUANT_MULTIPLIERS["q5_k_m"]
    if re.search(r'\bq8\b', low):
        return "q8", _QUANT_MULTIPLIERS["q8_0"]

    return "unknown", _DEFAULT_QUANT_MULTIPLIER


def _estimate_model_vram(
    model_name: str,
    role: str,
    context_tokens: int = 32768,
) -> float:
    """V13.26.0: Estimate VRAM for a model based on param count + quantization + KV cache.

    Formula:
        weight_vram = param_count_gb * quant_multiplier
        kv_cache_vram = param_count_gb * _KV_CACHE_FACTOR * (context_tokens / 32768)
        total = weight_vram + kv_cache_vram + _COMPUTE_OVERHEAD_GB

    For a 12B Q5_K_XL model at 32k context:
        weight_vram = 12 * 0.72 = 8.64 GB
        kv_cache_vram = 12 * 0.15 * 1.0 = 1.8 GB
        total = 8.64 + 1.8 + 0.5 = 10.94 GB ≈ 10.9 GB

    Falls back to the old _KNOWN_ESTIMATES dict for small/specialized models
    (TTS engines, NLLB, etc.) that don't have parameter-count tags.
    """
    if not model_name:
        return 0.0

    # ── Check known estimates first (for TTS, NLLB, etc.) ────────────────
    low = model_name.lower()
    for key, (vram, _) in _KNOWN_ESTIMATES.items():
        if key in low:
            return vram

    # ── Parse parameter count ────────────────────────────────────────────
    param_count = _parse_param_count(model_name)

    if param_count is None:
        # Can't parse — use the old fallback ladder
        if "12b" in low or "13b" in low:
            return 6.5  # old estimate (underestimate, but we can't do better)
        if "9b" in low or "8b" in low:
            return 5.5
        if "7b" in low:
            return 5.0
        if "4b" in low or "3b" in low:
            return 2.5
        if "1b" in low:
            return 1.5
        if "600m" in low:
            return 2.5
        return 5.0  # conservative default

    # ── Parse quantization ───────────────────────────────────────────────
    _, quant_mult = _parse_quantization(model_name)

    # ── Calculate weight VRAM ────────────────────────────────────────────
    # param_count is in billions; multiplier is bytes per param
    # VRAM (GB) = param_count * multiplier
    weight_vram = param_count * quant_mult

    # ── Calculate KV cache VRAM ──────────────────────────────────────────
    # KV cache scales with context length. At 32k it's ~1.5-2 GB for 12B.
    # At 8k it's ~0.4-0.5 GB. Proportional to context_tokens / 32768.
    context_ratio = max(context_tokens / 32768, 0.25)  # minimum 8k equivalent
    kv_cache_vram = param_count * _KV_CACHE_FACTOR * context_ratio

    # ── Total ────────────────────────────────────────────────────────────
    total = weight_vram + kv_cache_vram + _COMPUTE_OVERHEAD_GB

    return round(total, 1)


# V13.26.0: Known estimates for small/specialized models that don't have
# parameter-count tags in their names. These are used as-is (no KV cache
# calculation — these models typically use fixed-size context).
_KNOWN_ESTIMATES = {
    # OCR models (7B Q4) — use the calculator for these, but keep as fallback
    "olmocr": (6.4, "OCR"),
    "qwen3-vl": (6.0, "OCR"),
    "qwen2.5-vl": (5.5, "OCR"),
    # Translation models
    "translategemma:4b": (2.8, "Translation"),
    "translategemma:12b": (6.5, "Translation"),
    "nllb-200-distilled-600m": (2.5, "Translation"),
    "nllb-200-distilled-1.3b": (4.0, "Translation"),
    # TTS — these are not LLMs, use fixed estimates
    "neutts": (1.5, "TTS"),
    "kokoro": (0.5, "TTS"),
    "piper": (0.1, "TTS"),
}


def get_total_vram() -> float | None:
    """Get total VRAM in GB, or None if unavailable."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        return torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except ImportError:
        return None


def calculate_vram_budget(
    ocr_model: str = "",
    summarization_model: str = "",
    fast_model: str = "",
    heavy_model: str = "",
    translation_backend: str = "",
    translation_model: str = "",
    harakat_model: str = "",
    judge_model: str = "",
    tts_enabled: bool = False,
    tts_engine: str = "neutts",
    max_workers: int = 2,
    context_tokens: int = 32768,
) -> tuple[list[ModelVRAMEstimate], float, float | None, str]:
    """Calculate VRAM budget for a conversion configuration.

    V13.26.0: Added ``context_tokens`` parameter for KV cache estimation.
    Previously the calculator ignored context window entirely — a 12B model
    at 8k context got the same estimate as at 32k. Now the KV cache is
    calculated based on the actual context window setting.

    Args:
        context_tokens: V13.26.0 — the context window size for the
            summarization model (default 32768). Affects KV cache estimate.
            Larger context = more VRAM for KV cache.

    Returns:
        (estimates, peak_vram_gb, total_vram_gb, recommendation)
    """
    estimates: list[ModelVRAMEstimate] = []

    # V13.40.2: OCR and Summarization run in SEQUENTIAL phases, never simultaneously.
    # The old code marked both as loaded_simultaneously=True, summing their VRAM
    # (e.g., OCR 6.4 + Summ 9.3 = 15.7 GB) — a false OVERBUDGET error.
    # In reality, the OCR model is unloaded before the summarizer loads.
    # The peak is the MAX of the two phases, not the SUM.
    #
    # Phase grouping (only models in the SAME phase can be loaded simultaneously):
    #   Phase 1 (Extraction): OCR model only
    #   Phase 2 (Summarization): summarization + fast + heavy (model swap during phase)
    #   Phase 3 (Translation): translation + harakat + judge
    #   Phase 4 (TTS): TTS engine
    #
    # Within a phase, models MAY overlap (e.g., summarizer + fast model swap).
    # Across phases, they NEVER overlap (each phase completes before the next starts).

    # Phase 1: OCR + extraction (OCR model loaded)
    if ocr_model:
        vram = _estimate_model_vram(ocr_model, "OCR", context_tokens)
        estimates.append(ModelVRAMEstimate(ocr_model, "OCR", vram, True))

    # Phase 2: Summarization (summarizer + potentially fast model)
    # V13.40.2: These ARE simultaneous with each other (model swap within phase),
    # but NOT simultaneous with OCR (different phase).
    if summarization_model:
        vram = _estimate_model_vram(summarization_model, "Summarization", context_tokens)
        estimates.append(ModelVRAMEstimate(summarization_model, "Summarization", vram, True))
    if fast_model and fast_model != summarization_model:
        vram = _estimate_model_vram(fast_model, "Fast/Simplification", context_tokens)
        estimates.append(ModelVRAMEstimate(fast_model, "Fast/Simplification", vram, True))
    if heavy_model:
        vram = _estimate_model_vram(heavy_model, "Heavy model", context_tokens)
        estimates.append(ModelVRAMEstimate(heavy_model, "Heavy model", vram, True))

    # Phase 3: Translation (if enabled)
    # V13.40.2: Translation is a separate phase — never overlaps with OCR or Summarization.
    if translation_backend == "nllb":
        estimates.append(ModelVRAMEstimate(
            "NLLB-200-600M", "Translation", 2.5, True
        ))
    elif translation_backend == "ollama" and translation_model:
        vram = _estimate_model_vram(translation_model, "Translation", context_tokens)
        estimates.append(ModelVRAMEstimate(translation_model, "Translation", vram, True))

    # Harakat model (always Ollama, loaded during translation phase)
    if harakat_model:
        vram = _estimate_model_vram(harakat_model, "Harakat", context_tokens)
        estimates.append(ModelVRAMEstimate(harakat_model, "Harakat", vram, True))

    # Judge model (loaded during validation/translation phase)
    if judge_model and judge_model != summarization_model:
        vram = _estimate_model_vram(judge_model, "Judge", context_tokens)
        estimates.append(ModelVRAMEstimate(judge_model, "Judge", vram, True))

    # TTS (loaded during audio generation — separate phase)
    if tts_enabled:
        tts_vram = 1.5 if tts_engine == "neutts" else 0.5
        estimates.append(ModelVRAMEstimate(
            f"{tts_engine} (TTS)", "TTS", tts_vram, True
        ))

    # V13.40.2: Calculate peak VRAM correctly.
    # The old code summed ALL models marked loaded_simultaneously=True,
    # which summed across phases (OCR + Summarization + Translation + TTS).
    # That's wrong — phases are sequential, so the peak is the MAX across
    # phases, not the SUM.
    #
    # The `loaded_simultaneously` flag now means "loaded during its phase".
    # We compute each phase's total, then take the max.
    #
    # Phase mapping (by role):
    #   Phase 1 (Extraction):     OCR
    #   Phase 2 (Summarization):  Summarization, Fast/Simplification, Heavy model
    #   Phase 3 (Translation):    Translation, Harakat, Judge
    #   Phase 4 (TTS):            TTS
    _PHASE_MAP = {
        "OCR": 1,
        "Summarization": 2,
        "Fast/Simplification": 2,
        "Heavy model": 2,
        "Translation": 3,
        "Harakat": 3,
        "Judge": 3,
        "TTS": 4,
    }
    _phase_totals: dict[int, float] = {}
    for e in estimates:
        if not e.loaded_simultaneously:
            continue
        phase = _PHASE_MAP.get(e.role, 99)
        _phase_totals[phase] = _phase_totals.get(phase, 0) + e.estimated_vram_gb
    peak_vram = max(_phase_totals.values()) if _phase_totals else 0.0

    # Adjust for max_workers (each worker loads its own copy of the model)
    # Only applies to summarization (parallel chapter processing)
    if max_workers > 1 and summarization_model:
        # Each additional worker adds ~60% of the model VRAM (shared layers)
        extra = (max_workers - 1) * _estimate_model_vram(
            summarization_model, "Summarization", context_tokens
        ) * 0.6
        peak_vram += extra

    total = get_total_vram()

    # Recommendation
    recommendation = ""
    if total:
        if peak_vram > total:
            recommendation = (
                f"❌ OVERBUDGET: Peak VRAM {peak_vram:.1f} GB exceeds "
                f"available {total:.1f} GB. Reduce max_workers to 1, "
                f"use a smaller model, or disable some features."
            )
        elif peak_vram > total * 0.95:
            recommendation = (
                f"⚠️ TIGHT: Peak VRAM {peak_vram:.1f} GB is close to "
                f"available {total:.1f} GB ({peak_vram/total*100:.0f}%). "
                f"Consider reducing max_workers to 1."
            )
        elif peak_vram > total * 0.85:
            recommendation = (
                f"✅ Fits: Peak VRAM {peak_vram:.1f} GB / {total:.1f} GB "
                f"({peak_vram/total*100:.0f}%). Should work but monitor for OOM."
            )
        else:
            recommendation = (
                f"✅ Comfortable: Peak VRAM {peak_vram:.1f} GB / {total:.1f} GB "
                f"({peak_vram/total*100:.0f}%)."
            )
    else:
        recommendation = f"Peak VRAM estimate: {peak_vram:.1f} GB (GPU detection unavailable)"

    return estimates, peak_vram, total, recommendation


def format_vram_report(
    estimates: list[ModelVRAMEstimate],
    peak_vram: float,
    total: float | None,
    recommendation: str,
) -> str:
    """Format the VRAM budget as a human-readable report string.

    V13.40.2: The report now groups models by phase (sequential, not simultaneous).
    The peak is the MAX across phases, not the SUM.
    """
    lines = ["━━━ VRAM Budget (by phase — peak is max, not sum) ━━━"]
    current_phase = 0
    _PHASE_NAMES = {1: "Phase 1 (Extraction)", 2: "Phase 2 (Summarization)",
                     3: "Phase 3 (Translation)", 4: "Phase 4 (TTS)"}
    _PHASE_MAP = {
        "OCR": 1, "Summarization": 2, "Fast/Simplification": 2, "Heavy model": 2,
        "Translation": 3, "Harakat": 3, "Judge": 3, "TTS": 4,
    }
    for e in estimates:
        phase = _PHASE_MAP.get(e.role, 0)
        if phase != current_phase and phase in _PHASE_NAMES:
            lines.append(f"  [{_PHASE_NAMES[phase]}]")
            current_phase = phase
        lines.append(f"    {e.role}: {e.name} (~{e.estimated_vram_gb:.1f} GB)")
    lines.append(f"  {'─' * 40}")
    if total:
        lines.append(f"  Peak (max across phases): {peak_vram:.1f} GB / {total:.1f} GB available")
    else:
        lines.append(f"  Peak (max across phases): {peak_vram:.1f} GB (GPU detection unavailable)")
    lines.append(f"  {recommendation}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
