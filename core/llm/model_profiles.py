"""V3.6.0 Model Profiles — per-model configurations for optimal quality.

Different LLM models need different settings (temperature, prompts, filters).
This module provides profiles for known models and auto-detection based on
model name patterns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Configuration profile for a specific LLM model."""

    name: str
    temperature: float = 0.6
    max_bullets: int = 30
    thinking_strip_aggressive: bool = False
    prompt_suffix: str = ""
    dedup_threshold: int = 45  # rapidfuzz threshold
    simplification_temperature: float = 0.1
    narrative_filter_strict: bool = True


# Built-in profiles for known models
_PROFILES: dict[str, ModelProfile] = {
    # Qwen3.5-9B — thinking model, excellent summarization, fails at simplification
    "qwen": ModelProfile(
        name="Qwen3.5-9B",
        temperature=0.6,
        max_bullets=30,
        thinking_strip_aggressive=True,  # aggressive thinking strip needed
        prompt_suffix="NOTE: You are a thinking model. Do NOT include your chain-of-thought reasoning in the output. Output ONLY the final summary.",
        dedup_threshold=60,  # Qwen produces clean bullets, less dedup needed
        simplification_temperature=0.1,
        narrative_filter_strict=True,
    ),
    # Qwythos-9B — Claude-style model, good at simplification, verbose
    "qwythos": ModelProfile(
        name="Qwythos-9B-Claude-Mythos",
        temperature=0.6,
        max_bullets=20,  # cap lower to reduce verbosity
        thinking_strip_aggressive=False,  # doesn't use <think> blocks
        # V13.22.0: Removed bullet-COUNT guidance from the suffix — it
        # contradicted both the prompt-bank templates ("20-40 bullets") and
        # the content-preset addendum ("Aim for 30 bullets" for academic).
        # The LLM complained about the contradiction in logs.  Bullet count
        # is now governed solely by the prompt template + content preset.
        prompt_suffix="NOTE: Be concise — each bullet should be a single, distinct concept (one sentence, max ~25 words). Do not pad bullets with narrative filler.",
        dedup_threshold=45,  # more aggressive dedup for verbose model
        simplification_temperature=0.1,
        narrative_filter_strict=True,
    ),
    # Llama 3.x — general purpose, good balance
    "llama": ModelProfile(
        name="Llama-3.x",
        temperature=0.4,
        max_bullets=25,
        thinking_strip_aggressive=False,
        prompt_suffix="",
        dedup_threshold=50,
        simplification_temperature=0.15,
        narrative_filter_strict=True,
    ),
    # Gemma — Google model, concise
    "gemma": ModelProfile(
        name="Gemma",
        temperature=0.4,
        max_bullets=20,
        thinking_strip_aggressive=False,
        prompt_suffix="",
        dedup_threshold=50,
        simplification_temperature=0.15,
        narrative_filter_strict=False,  # less strict — Gemma is more conservative
    ),
    # Default profile
    "default": ModelProfile(
        name="Default",
        temperature=0.6,
        max_bullets=30,
        thinking_strip_aggressive=False,
        prompt_suffix="",
        dedup_threshold=45,
        simplification_temperature=0.1,
        narrative_filter_strict=True,
    ),
}


def get_model_profile(model_name: str) -> ModelProfile:
    """Get the appropriate profile for a model based on its name.

    Auto-detects the model family from the model name string and returns
    the corresponding profile. Falls back to 'default' if no match.
    """
    name_lower = (model_name or "").lower()

    if "qwen" in name_lower:
        return _PROFILES["qwen"]
    elif "qwythos" in name_lower or "mythos" in name_lower or "claude" in name_lower:
        return _PROFILES["qwythos"]
    elif "llama" in name_lower:
        return _PROFILES["llama"]
    elif "gemma" in name_lower:
        return _PROFILES["gemma"]
    else:
        return _PROFILES["default"]
