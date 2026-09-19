"""V18.20.2.0 (SWOT A3): shared num_ctx clamp for low-bit 27B+ models.

The V18.2.43 cap decision (IQ2_S → 26758, other low-bit 27B+ → 16000 on
≤12 GB cards) lived ONLY inside ``OllamaProvider._adaptive_context``. The
streaming-fallback nonstreaming path in
``core/summarisation/llm_dispatcher.py`` used a raw
``ctx = max(context_tokens, 16000)`` with NO cap — a user-set 65536 plus a
streaming failure would send an uncapped num_ctx to Ollama and OOM-loop the
12 GB card (SWOT finding: "streaming fallback nonstreaming path uses raw
ctx — NO 26758 IQ2_S cap, NO VRAM guard").

This module is the single home of the cap decision so BOTH paths (the
provider's adaptive path and the dispatcher's fallback) share it — the
constants are NOT duplicated (they delegate to ``core.llm.model_taxonomy``,
the established single source of truth for model classification).

Hard constraints honored (unchanged):
  - num_ctx ceiling 32768; app caps to 26758 for IQ2_S on ≤12 GB cards.
  - The VRAM-aware 26758→32768 raise stays in OllamaProvider (it requires
    the provider's external /api/ps reading — SWOT A1); callers of this
    clamp get the SAFE 26758 ceiling (quality > speed).
"""

from __future__ import annotations

from core.llm.model_taxonomy import is_27b_plus, is_iq2_s, is_low_bit_quant

# The V18.2.43 caps (see iq2_s_profile.CONTEXT_CAP for the IQ2_S value's
# home). Kept here as the shared constants for the clamp decision tree.
IQ2_S_SAFE_CTX = 26758
LOW_BIT_DEFAULT_CTX = 16000
# ≤12 GB cards must cap; larger cards (16+ GB) have enough headroom.
CAP_MAX_TOTAL_GB = 12.0


def gpu_total_gb() -> float | None:
    """Total GPU VRAM in GB via torch, or None when unavailable.

    ``torch.cuda.get_device_properties(0).total_memory`` is a STATIC
    hardware property (the card's installed VRAM) — unlike
    ``torch.cuda.memory_allocated`` it is NOT an app-process measurement,
    so it is safe to trust for the cap decision. Returns None when torch
    is absent or CUDA is unavailable (headless CPU box, test sandbox) —
    callers treat None as "no cap decision possible".
    """
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except Exception:
        pass
    return None


def low_bit_ctx_cap(model: str | None, total_gb: float | None) -> int | None:
    """The V18.2.43 num_ctx cap for ``model`` on a card with ``total_gb`` VRAM.

    Returns:
        26758 for IQ2_S 27B+ low-bit quants on ≤12 GB cards,
        16000 for other low-bit 27B+ quants (Q2_K_XL etc.) on ≤12 GB cards,
        None when no cap applies (big GPU, small/full-precision model,
        or total_gb unknown — the caller keeps its own ctx).
    """
    if total_gb is None or total_gb > CAP_MAX_TOTAL_GB:
        return None
    if not model:
        return None
    if not (is_low_bit_quant(model) and is_27b_plus(model)):
        return None
    return IQ2_S_SAFE_CTX if is_iq2_s(model) else LOW_BIT_DEFAULT_CTX


def clamp_num_ctx(
    model: str | None,
    ctx: int,
    total_gb: float | None = None,
) -> int:
    """Clamp ``ctx`` to the model-specific safe ceiling (V18.2.43 caps).

    ``total_gb`` may be passed by callers that already know it (the
    provider's adaptive path); when omitted it is detected via torch.
    On detection failure (no torch / no CUDA) the ctx is returned
    unchanged — the cap decision is only possible with a known GPU size.
    """
    if total_gb is None:
        total_gb = gpu_total_gb()
    cap = low_bit_ctx_cap(model, total_gb)
    if cap is not None and ctx > cap:
        return cap
    return ctx
