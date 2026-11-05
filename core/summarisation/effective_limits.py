"""V0.7.3 (wizard rework ⑤, D12) — the effective-limits mirror.

The backend's Summarizer CLAMPS the requested context/output limits at
construction (``summarizer_init.py:538-674``):

- context: a request ≤ 16000 is replaced by the VRAM-ladder auto value;
  anything below 32768 is raised to ``max(auto, 32768)`` (the hardware
  floor); a known-model registry can raise it further at start time;
- output: compact mode caps at 2048; low-bit quants and small models
  (< 13B) cap at 8192; full-precision large models are forced UP to at
  least 16000.

The user's requested numbers are therefore ADVISORY — the wizard used to
show them as if they were the truth. This module is the single source
both sides share: Step 5's read-only "Effective after model limits"
line computes its display from :func:`effective_limits`, and the
Summarizer's ``_auto_detect_context_limit`` delegates to
:func:`auto_context_limit` (one ladder, no drift).

The mirror is deliberately DETERMINISTIC-ONLY: it covers the three
mechanisms the plan names (VRAM ladder, ≥32768 context floor,
2048/8192/16000 output by model class). The registry's model-specific
raise and the live-server probes stay backend-side — the line's tooltip
says a known model can raise context further at start.
"""

from __future__ import annotations

from core.llm.iq2_s_profile import IQ2_S_PROFILE
from core.llm.model_taxonomy import (
    LEGACY_DEFAULT_MODEL,
    is_low_bit_quant,
    is_small_model,
    param_count_b,
)

# The "replace with the auto value" threshold (summarizer_init.py:445:
# ``<= 16000``) and the hardware floor (:538: ``< 32768``).
_AUTO_CTX_THRESHOLD = 16000
_CTX_FLOOR = 32768


def auto_context_limit() -> int:
    """Recommended context size (tokens) based on available VRAM.

    The V10.23.0 aggressive-VRAM ladder, moved VERBATIM from
    ``summarizer.py:_auto_detect_context_limit`` (behavior-identical; the
    Summarizer method now delegates here — one ladder, no drift):

    - < 8 GB VRAM:   32768   (small GPUs — 8k KV cache after 5GB model)
    - < 12 GB VRAM:  65536   (RTX 3060 12GB — ~3GB KV cache)
    - < 16 GB VRAM:  131072  (RTX 3060 12GB, RTX 4070 12GB — ~4.5GB KV cache)
    - < 24 GB VRAM:  131072  (RTX 3090/4090 24GB — ~10GB KV cache)
    - >= 24 GB VRAM: 262144  (RTX 4090 24GB+ — huge context)
    - No torch/CUDA: 65536   (sensible default)
    """
    try:
        import torch

        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            if vram_gb < 8:
                return 32768
            elif vram_gb < 12:
                return 65536
            elif vram_gb < 16:
                return 131072  # V10.23.0: was 65536 → 131072 (aggressive)
            elif vram_gb < 24:
                return 131072
            else:
                return 262144  # V10.23.0: was 131072 → 262144 (aggressive)
        else:
            return 65536
    except ImportError:
        return 65536
    except Exception:
        return 65536


def effective_limits(
    requested_ctx: int,
    requested_out: int,
    model_name: str = "",
    compact_summaries: bool = False,
    auto_ctx: int | None = None,
) -> tuple[int, int]:
    """The effective (ctx, out) after the backend's clamp ladder.

    Mirrors ``summarizer_init.py`` exactly (order included — the compact
    cap is applied BEFORE the class clamps, which is what lets a compact
    2048 survive the 16000-force):

    1. ctx ≤ 16000 → the VRAM-ladder auto value;
    2. ctx < 32768 → ``max(auto, 32768)``;
    3. compact → out capped at ``IQ2_S_PROFILE.COMPACT_MAX_OUTPUT`` (2048);
    4. low-bit quant OR small model (< 13B) → out capped at
       ``LOW_BIT_MAX_OUTPUT`` (8192);
    5. full-precision large model → out forced up to
       ``LARGE_FP_MIN_OUTPUT`` (16000) — unless compact is on.

    The model-name semantics match the backend's ``primary_model``
    resolution: an empty name falls back to the legacy default sentinel
    before classification. ``auto_ctx`` is injectable so tests (and any
    caller without torch) get deterministic results.
    """
    if auto_ctx is None:
        auto_ctx = auto_context_limit()

    # ── Context: the auto substitution, then the hardware floor ──────────
    ctx = int(requested_ctx)
    if ctx <= _AUTO_CTX_THRESHOLD:
        ctx = int(auto_ctx)
    if ctx < _CTX_FLOOR:
        ctx = max(int(auto_ctx), _CTX_FLOOR)

    # ── Output: compact cap first, then the model-class clamps ───────────
    out = int(requested_out)
    compact_cap: int | None = None
    if compact_summaries:
        compact_cap = IQ2_S_PROFILE.COMPACT_MAX_OUTPUT  # 2048
        out = min(out, compact_cap)

    model = (model_name or "").strip() or LEGACY_DEFAULT_MODEL
    if is_low_bit_quant(model) or is_small_model(model):
        if out > IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT:  # 8192
            out = IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT
    else:
        if out < IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT and not compact_cap:  # 16000
            out = IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT

    return ctx, out


def format_effective_limits(ctx: int, out: int) -> str:
    """The Step-5 read-only line, e.g. ``Effective after model limits:
    32,768 ctx / 16,000 out``."""
    return f"Effective after model limits: {int(ctx):,} ctx / {int(out):,} out"


def classify_output_cap(model_name: str = "", compact_summaries: bool = False) -> str:
    """Human phrase for WHY the output is what it is (the tooltip copy)."""
    model = (model_name or "").strip() or LEGACY_DEFAULT_MODEL
    if compact_summaries:
        return f"compact mode caps output at {IQ2_S_PROFILE.COMPACT_MAX_OUTPUT:,}"
    if is_low_bit_quant(model):
        return f"low-bit quant caps output at {IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT:,}"
    if is_small_model(model):
        return (
            f"small model ({param_count_b(model):.0f}B < 13B threshold) "
            f"caps output at {IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT:,}"
        )
    return f"full-precision large model forces output to at least {IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT:,}"
