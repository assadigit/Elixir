"""Named custom-provider catalog — settings persistence + keychain keys.

V0.16 (Phase 3 / task 3.2): extracted from ui_qt/settings/sections.py as a
Qt-free module so the credential-handling logic is importable (and testable
in CI) without PySide6's GUI shared libraries. The catalog itself lives in
settings under ``ai.custom_providers`` (list of dicts with name / base_url /
model), but the API KEYS are stored in the OS keychain under per-provider
paths — the persisted blob carries no key material.

Back-compat: legacy catalogs with inline plaintext ``api_key`` entries are
migrated to the keychain on first load (never the reverse — a key is only
removed from plaintext AFTER the keychain write succeeds).
"""

from __future__ import annotations

from typing import Any

# The controller duck-type these helpers need: get_setting / update_setting
# / get_secret / set_secret (controller.Controller provides all four;
# tests use lighter stand-ins with the same surface).


def provider_key_path(name: object) -> str:
    """Keychain path for a named custom provider's API key.

    The path contains "api_key", so core.system.secrets._is_secret_path
    routes it to the keychain automatically (plaintext fallback on
    backend-less systems, same policy as every other credential).
    """
    clean = str(name or "").strip() or "provider"
    return f"ai.custom_providers.{clean}.api_key"


def load_custom_providers(controller: Any) -> list:
    """Return the saved custom-provider catalog with keys resolved.

    API keys are resolved through the OS keychain (per-provider path).
    Legacy catalogs that still carry inline plaintext keys are migrated
    on first load — the key moves to the keychain and the persisted blob
    is rewritten without key material.
    """
    providers = list(controller.get_setting("ai.custom_providers", []) or [])
    migrated = False
    for p in providers:
        if not isinstance(p, dict):
            continue
        path = provider_key_path(p.get("name"))
        inline = p.get("api_key", "")
        if inline:
            # One-time legacy migration: inline plaintext → keychain.
            try:
                controller.set_secret(path, inline)
            except Exception:  # pragma: no cover — best-effort
                continue  # keep the inline value working (plaintext fallback)
            migrated = True
        try:
            p["api_key"] = controller.get_secret(path, "")
        except Exception:  # pragma: no cover — best-effort
            p["api_key"] = ""
    if migrated:
        try:
            save_custom_providers(controller, providers)
        except Exception:  # pragma: no cover — best-effort
            pass
    return providers


def save_custom_providers(controller: Any, providers: list) -> None:
    """Persist the catalog; API keys go to the keychain, not the blob."""
    stripped = []
    for p in providers:
        if not isinstance(p, dict):
            stripped.append(p)
            continue
        entry = dict(p)
        key = entry.pop("api_key", "")
        if key:
            try:
                controller.set_secret(provider_key_path(entry.get("name")), key)
            except Exception:  # pragma: no cover — best-effort
                entry["api_key"] = key  # never lose a key: plaintext fallback
        stripped.append(entry)
    controller.update_setting("ai.custom_providers", stripped)
