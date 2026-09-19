"""V18.20.1.0 (Debt D9): Centralized IQ2_S hardware profile.

The V18.20.0.0 SWOT (debt D9) noted that the IQ2_S constants (2400s deadline,
1200s HTTP timeout, 26758 context cap, 8192 max output) are sprinkled across
summarizer.py and model_taxonomy. This module centralizes them into a single
profile so they can be tuned in one place when the hardware changes.

Single source of truth for the IQ2_S 27B model on the RTX 3060 12GB rig.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IQ2SProfile:
    """Hardware-specific profile for the IQ2_S 27B model (RTX 3060 12GB).

    All values are the verified golden-standard constants. Change them HERE
    (one place) when the hardware changes — not scattered across summarizer.py.

    Rationale (documented for future tuning):
      - CHAPTER_DEADLINE_SEC=2400 (40 min): the IQ2_S 27B is slow (~1.5 min/chapter
        for 9k-token chapters). The pre-V18.15.4.0 480s deadline was too tight.
      - HTTP_TIMEOUT_SEC=1200 (20 min): a single LLM call can take 8-12 min on
        a dense chapter. The pre-V18.15.6.0 600s timeout killed mid-generation.
      - CONTEXT_CAP=26758: the IQ2_S quant has a hard 32768 context window, but
        26758 is the safe ceiling (16000 output + 11000 input = 27000 > 26758
        overflows → empty response). Capped here so max_output capping can
        reference it without recomputing.
      - MAX_OUTPUT_TOKENS=8192: fits 11000+8192=19192 < 26758. Raising to 12000
        caused thermal throttling (V18.3.6 reverted). More output = more heat.
      - IQ2_XXS_TIMEOUT_SEC=300: the IQ2_XXS (Q2_K) quant is SLOWER than IQ2_S
        and stalls — cap at 300s so it fails fast (not 20 min of stall).
      - IQ2_XXS_DEADLINE_SEC=1200: IQ2_XXS chapters take ~2x longer than IQ2_S
        but still need a cap to prevent indefinite hangs.
    """

    CHAPTER_DEADLINE_SEC: int = 2400
    HTTP_TIMEOUT_SEC: int = 1200
    CONTEXT_CAP: int = 26758
    MAX_OUTPUT_TOKENS: int = 8192
    # IQ2_XXS (the slower low-bit quant, not IQ2_S) overrides
    IQ2_XXS_TIMEOUT_SEC: int = 300
    IQ2_XXS_DEADLINE_SEC: int = 1200
    # The safe max_output for low-bit/small models (8192 — see CONTEXT_CAP rationale)
    LOW_BIT_MAX_OUTPUT: int = 8192
    # The force-to floor for full-precision large models
    LARGE_FP_MIN_OUTPUT: int = 16000
    # Compact summaries cap (V18.20.1.0 D10: now survives the 16000-force)
    COMPACT_MAX_OUTPUT: int = 2048


# The single profile instance (immutable — read-only).
IQ2_S_PROFILE = IQ2SProfile()
