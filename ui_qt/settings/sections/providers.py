"""V0.4.19 — cloud-provider catalog constants for the settings sections.

``PROVIDER_LABELS`` / ``PROVIDER_KEYS`` / ``PROVIDER_URLS`` /
``PROVIDER_MODEL_HINTS`` moved VERBATIM from ``ui_qt/settings/sections.py``
during the V0.4.19 de-monolithization; re-exported from the
``ui_qt.settings.sections`` facade so the historical import surface is
unchanged.
"""

from __future__ import annotations

# ════════════════════════════════════════════════════════════════════════════
# AI sections
# ════════════════════════════════════════════════════════════════════════════

PROVIDER_LABELS = {
    "Local (Ollama)": "ollama",
    "OpenAI-compatible": "openai_compatible",
    "Claude (Anthropic)": "claude",
}
PROVIDER_KEYS = {v: k for k, v in PROVIDER_LABELS.items()}
PROVIDER_URLS = {
    "ollama": "",
    "openai_compatible": "https://openrouter.ai/api/v1",
    "claude": "https://api.anthropic.com/v1",
}
PROVIDER_MODEL_HINTS = {
    "ollama": "(set in summarisation model above)",
    "openai_compatible": "google/gemini-2.5-flash-preview:free",
    "claude": "claude-3-5-sonnet-20241022",
}
