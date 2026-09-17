"""V7.6.0 R1 / V7.7.0: Output cost grading — logical tiers, not minute estimates.

The user's clarification (V7.7.0): minute estimates are misleading because
they vary wildly by hardware/model.  What's stable is the *logical* cost —
some outputs inherently take more work regardless of the machine:

  - **Core**: deterministic, no LLM — always negligible extra cost.
  - **Fast**: single-pass deterministic or trivial formatting.
  - **Moderate**: one LLM call (whole-book synthesis).
  - **Heavy**: per-chapter LLM calls (scales with chapter count).
  - **Very heavy**: realtime audio generation (TTS).

The UI shows tier labels + colors, never minute numbers.  The total is a
*load grade* (Light / Moderate / Heavy / Very heavy) derived from the
highest tier selected + how many heavy outputs are on — not a minute sum.

The ``mins`` field is kept internally only for sort ordering (cheapest
first); it's never displayed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

# ── Static cost tiers ──────────────────────────────────────────────────────
# `mins` is internal-only (used for sort ordering within a tier).
# The UI displays `tier` + `tier_label`, never the minutes.

logger = logging.getLogger(__name__)

_STATIC_ESTIMATES: dict[str, dict] = {
    # Core outputs — deterministic, no LLM
    "summarisation.enabled":          {"mins": 0,   "label": "Per-chapter Summaries", "tier": "core",       "note": "runs during main summarization phase"},
    "summarisation.include_keypoints":{"mins": 1,   "label": "Keypoints",             "tier": "core",       "note": "deterministic extraction"},
    "docx.enabled":                   {"mins": 1,   "label": "DOCX Document",        "tier": "core",       "note": "no LLM, just formatting"},
    "outputs.mindmap":                {"mins": 2,   "label": "Mind Map",             "tier": "fast",       "note": "deterministic, no LLM"},
    # Moderate — one LLM call (whole-book)
    "outputs.briefing":               {"mins": 5,   "label": "Executive Briefing",   "tier": "moderate",   "note": "one LLM call"},
    "outputs.flashcards":             {"mins": 6,   "label": "Flashcards",           "tier": "moderate",   "note": "one LLM call"},
    "outputs.obsidian":               {"mins": 7,   "label": "Obsidian KB",          "tier": "moderate",   "note": "deterministic formatting + linking"},
    # Heavy — per-chapter LLM calls (scales with chapter count)
    "summarisation.simplified_keypoints_enabled": {"mins": 15, "label": "Simplified Keypoints", "tier": "heavy", "note": "extra LLM pass per chapter"},
    "outputs.podcast":                {"mins": 18,  "label": "Podcast Script",       "tier": "heavy",      "note": "LLM call per chapter (default scope)"},
    "outputs.packets":                {"mins": 20,  "label": "Packets of Knowledge", "tier": "heavy",      "note": "clustering + synthesis per packet"},
    "outputs.study_guide":            {"mins": 12,  "label": "Study Guide",          "tier": "heavy",      "note": "one LLM call, structured output"},
    "outputs.social":                 {"mins": 10,  "label": "Social Media Pack",    "tier": "heavy",      "note": "one LLM call"},
    # Very heavy — realtime audio
    "outputs.tts":                    {"mins": 30,  "label": "Podcast Audio (TTS)",  "tier": "very_heavy", "note": "audio synthesis (NeuTTS/Piper)"},
}


def get_output_estimate(setting_key: str) -> dict:
    """Return the estimate dict for a setting key."""
    return _STATIC_ESTIMATES.get(setting_key, {
        "mins": 5, "label": setting_key, "tier": "moderate", "note": ""
    })


# ── Tier metadata ──────────────────────────────────────────────────────────

_TIER_ORDER = ["core", "fast", "moderate", "heavy", "very_heavy"]

# V7.7.0: tier labels for UI display (no minute numbers).
_TIER_LABEL = {
    "core":       "Core",
    "fast":       "Fast",
    "moderate":   "Moderate",
    "heavy":      "Heavy",
    "very_heavy": "Very heavy",
}

# Short description of WHY each tier is that cost (for tooltips).
_TIER_DESC = {
    "core":       "Deterministic — no LLM, negligible extra cost.",
    "fast":       "Single-pass deterministic or trivial formatting.",
    "moderate":   "One LLM call (whole-book synthesis).",
    "heavy":      "Per-chapter LLM calls — scales with chapter count.",
    "very_heavy": "Realtime audio generation — slowest tier.",
}

# Theme color name for each tier (maps to palette in the UI).
_TIER_COLOR = {
    "core":       "success",
    "fast":       "success",
    "moderate":   "info",
    "heavy":      "warning",
    "very_heavy": "error",
}


def get_tier_order() -> list:
    """Return the tier ordering (least → most intensive)."""
    return _TIER_ORDER


def get_tier_label(tier: str) -> str:
    """Return the short UI label for a tier (e.g. 'Heavy')."""
    return _TIER_LABEL.get(tier, tier)


def get_tier_desc(tier: str) -> str:
    """Return the description of why this tier has this cost (for tooltips)."""
    return _TIER_DESC.get(tier, "")


def get_tier_color(tier: str) -> str:
    """Return the theme color name for a tier (for the UI)."""
    return _TIER_COLOR.get(tier, "text_muted")


def sort_outputs_by_cost(outputs: list) -> list:
    """Sort outputs by cost tier (least → most intensive).

    Within the same tier, sorts by the internal ``mins`` field.
    """
    def _cost(item):
        key = item[0]
        est = get_output_estimate(key)
        return (
            _TIER_ORDER.index(est["tier"]) if est["tier"] in _TIER_ORDER else 99,
            est["mins"],
        )
    return sorted(outputs, key=_cost)


# ── Load-grade total (V7.7.0: replaces minute-sum) ────────────────────────

def get_load_grade(enabled_keys: list) -> dict:
    """Compute the overall load grade for a set of enabled outputs.

    Returns ``{grade, label, color, counts}`` where:
      - ``grade`` is one of "none" / "light" / "moderate" / "heavy" / "very_heavy"
      - ``label`` is the UI string (e.g. "Heavy load")
      - ``color`` is the theme color name
      - ``counts`` is a per-tier count dict

    The grade is the **highest** tier selected, bumped up one level if
    there are 2+ heavy outputs (compound load).
    """
    counts = dict.fromkeys(_TIER_ORDER, 0)
    for key in enabled_keys:
        est = get_output_estimate(key)
        tier = est["tier"]
        if tier in counts:
            counts[tier] += 1

    # Determine grade: highest tier selected
    grade = "none"
    for tier in _TIER_ORDER:
        if counts[tier] > 0:
            grade = tier

    # Compound: 2+ heavy outputs bump to very_heavy
    if counts["heavy"] >= 2 and grade == "heavy":
        grade = "very_heavy"
    # 3+ moderate outputs bump to heavy
    if counts["moderate"] >= 3 and grade == "moderate":
        grade = "heavy"

    _GRADE_MAP = {
        "none":       ("Light load",       "success"),
        "core":       ("Light load",       "success"),
        "fast":       ("Light load",       "success"),
        "moderate":   ("Moderate load",    "info"),
        "heavy":      ("Heavy load",       "warning"),
        "very_heavy": ("Very heavy load",  "error"),
    }
    label, color = _GRADE_MAP.get(grade, ("Light load", "success"))
    return {"grade": grade, "label": label, "color": color, "counts": counts}


# ── Dynamic refinement from past conversion logs (framework) ───────────────

def get_dynamic_estimates(output_base_dir: Path) -> dict[str, float]:
    """Scan past conversion diagnostic logs for actual phase timings.

    Returns a dict ``{setting_key: avg_minutes}`` from the rolling average
    of past conversions.  Empty if no logs found.

    Note: these are used for internal calibration only, not displayed in
    the UI (the user's V7.7.0 direction is tier-based, not minute-based).
    """
    timings: dict[str, list] = {}
    if not output_base_dir.exists():
        return {}
    for diag_path in output_base_dir.glob("*/logs/*.diagnostic.jsonl"):
        try:
            for line in diag_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                phase = entry.get("phase", "")
                duration = entry.get("duration_seconds", 0)
                if phase and duration > 0:
                    key = _phase_to_setting_key(phase)
                    if key:
                        timings.setdefault(key, []).append(duration / 60.0)
        except (ValueError, KeyError):
            continue
    return {k: sum(v) / len(v) for k, v in timings.items() if v}


def _phase_to_setting_key(phase: str) -> str | None:
    """Map a diagnostic phase name to a setting key."""
    mapping = {
        "output_briefing": "outputs.briefing",
        "output_podcast": "outputs.podcast",
        "output_packets": "outputs.packets",
        "output_flashcards": "outputs.flashcards",
        "output_obsidian": "outputs.obsidian",
        "output_study_guide": "outputs.study_guide",
        "output_social": "outputs.social",
        "output_mindmap": "outputs.mindmap",
        "output_tts": "outputs.tts",
    }
    return mapping.get(phase)
