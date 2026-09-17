"""V7.5.0: Cloud LLM client — OpenAI-compatible API support (9Router + others).

9Router (https://9router.com/) is an OpenAI-compatible API router with a
``base_url`` + ``api_key`` that intelligently routes between models (Claude,
Gemini, Codex, and others).  This module provides:

- :func:`test_cloud_connection` — sends a tiny "Hello" request to verify the
  endpoint + key + model work *before* a 6-7 hour conversion commits to them.
- :data:`CLOUD_PRESETS` — quick-fill presets for 9Router and other common
  OpenAI-compatible routers, so the user doesn't have to hunt for base URLs.

The summarizer's existing ``_call_openai_compat`` handles the actual LLM
calls during conversion; this module is for *pre-flight verification* and
*UI convenience* only.
"""

from __future__ import annotations

import logging

# ── Quick-fill presets ─────────────────────────────────────────────────────
# Each preset is (label, base_url, sample_model).  The user picks one and the
# wizard fills the base_url + a placeholder model they can edit.

logger = logging.getLogger(__name__)

CLOUD_PRESETS: list[dict[str, str]] = [
    {
        "label": "9Router (Claude / Gemini / Codex)",
        "base_url": "https://9router.com/v1",
        "model": "claude-sonnet-4-5",
        "hint": "OpenAI-compatible router — use any model name 9Router supports.",
    },
    {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "google/gemini-2.5-flash-preview",
        "hint": "Aggregate router; many free + paid models.",
    },
    {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "hint": "Native OpenAI API.",
    },
    {
        "label": "Custom OpenAI-compatible",
        "base_url": "",
        "model": "",
        "hint": "Any server exposing /chat/completions (LM Studio, vLLM, etc.).",
    },
]


def test_cloud_connection(
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 30,
) -> tuple[bool, str]:
    """Send a tiny request to verify the cloud endpoint works.

    Returns ``(success, message)``.  ``message`` is a short human-readable
    string suitable for showing in the wizard's Test button tooltip/label.
    Never raises — all errors are caught and reported via the tuple.
    """
    base = (base_url or "").strip()
    if not base:
        return False, "No base URL set."
    if not model:
        return False, "No model name set."
    if not api_key:
        return False, "No API key set."

    import requests

    url = f"{base.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    # Some routers (e.g. OpenRouter) like a referer/title header; harmless elsewhere.
    if "openrouter" in base.lower():
        headers["HTTP-Referer"] = "https://markitdown-pro.local"
        headers["X-Title"] = "MarkItDown Pro Ultimate"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
        "max_tokens": 10,
        "temperature": 0.0,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection failed: {e}"
    except requests.exceptions.Timeout:
        return False, f"Timed out after {timeout}s — endpoint may be unreachable."
    except Exception as e:
        return False, f"Request error: {e}"

    if resp.status_code == 401:
        return False, "Unauthorized (401) — check your API key."
    if resp.status_code == 404:
        return False, "Not found (404) — check the base URL ends in /v1 (or equivalent)."
    if resp.status_code == 400:
        # Often means the model name is wrong
        try:
            detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception as _e:
            detail = resp.text[:200]
        return False, f"Bad request (400): {detail}"
    if not resp.ok:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    try:
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return False, f"Unexpected response shape: {e}"

    # A successful response — even if the model didn't say exactly "OK"
    preview = content[:60] + ("…" if len(content) > 60 else "")
    return True, f"Connected ✓ — model replied: {preview!r}"
