"""V10.34.0 (Sprint 6.1): OS keychain integration for API keys.

Before V10.34.0, all 6 API keys (OpenAI-compat, Claude, FreeLLMAPI,
grounding cloud, translation cloud, TTS cloud) were stored in plaintext
in ``~/.elixir/settings.json``.  Anyone with read access to that
file could steal the keys.

This module provides ``get_secret()`` / ``set_secret()`` that use the OS
keychain (via the ``keyring`` library) when available, and fall back to
plaintext settings.json when ``keyring`` is not installed.

Migration: on first access, if a key exists in settings.json but not in
the keychain, it's migrated (moved to keychain + removed from settings).
This is transparent — the user doesn't need to do anything.

Usage (replaces direct settings.json access for API keys)::

    from core.system.secrets import get_secret, set_secret
    api_key = get_secret("summarisation.api_key", settings)
    set_secret("summarisation.api_key", "sk-...", settings)

The ``keyring`` library is an optional dependency — if not installed,
the module falls back to plaintext (with a one-time WARNING log).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# The service name used in the OS keychain.
# V18.20.4.11 (rebrand): renamed MarkItDownPro → Elixir. Secrets stored
# under the legacy service are still FOUND (read-fallback in get_secret
# below) and re-stored under the new name on first read — no orphaned
# credentials, no re-entry required.
_KEYCHAIN_SERVICE = "Elixir"
_LEGACY_KEYCHAIN_SERVICE = "MarkItDownPro"  # pre-rebrand keychain service — read-fallback source (do NOT rename)

# Try to import keyring (optional dep)
try:
    import keyring as _keyring
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False
    logger.info(
        "keyring not installed — API keys will be stored in plaintext "
        "(settings.json). Install with: pip install keyring"
    )

# Keys that should be stored in the keychain (not settings.json).
# These are the 6 API-key-like settings paths.
_SECRET_PATHS = {
    "summarisation.api_key",
    "summarisation.claude_api_key",
    "summarisation.freellmapi_key",
    "grounding.cloud_api_key",
    "translation.cloud_api_key",
    "tts.cloud_api_key",
}


def _is_secret_path(path: str) -> bool:
    """Check if a settings path is an API-key-like secret."""
    return path in _SECRET_PATHS or any(
        keyword in path.lower() for keyword in ("api_key", "secret", "token", "password")
    )


def get_secret(path: str, settings: Any, default: str = "") -> str:
    """Get a secret value, preferring the OS keychain over settings.json.

    If the secret exists in settings.json but not in the keychain, it's
    migrated to the keychain on first access (and removed from settings).
    """
    if not _is_secret_path(path):
        # Not a secret path — use the normal settings lookup
        return settings.get(path, default)

    if _HAS_KEYRING:
        try:
            value = _keyring.get_password(_KEYCHAIN_SERVICE, path)
            if value is not None:
                return value
            # V18.20.4.11 (rebrand): not under the new service — try the
            # legacy Elixir service; if found, re-store under the
            # new name (one-time keychain migration, best-effort).
            try:
                legacy_value = _keyring.get_password(_LEGACY_KEYCHAIN_SERVICE, path)
            except Exception:
                legacy_value = None
            if legacy_value is not None:
                try:
                    _keyring.set_password(_KEYCHAIN_SERVICE, path, legacy_value)
                    logger.info("Keychain rebrand migration: re-stored '%s' under the Elixir service.", path)
                except Exception:
                    pass  # best-effort — the legacy entry still works via the fallback above
                return legacy_value
            # Not in keychain — check settings.json (migration opportunity)
            plaintext = settings.get(path, "")
            if plaintext:
                # Migrate: store in keychain, then clear from settings
                _keyring.set_password(_KEYCHAIN_SERVICE, path, plaintext)
                try:
                    settings.set(path, "")
                    logger.info("Migrated secret '%s' from settings.json to OS keychain.", path)
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)  # best-effort — don't crash on migration
                return plaintext
            return default
        except Exception as exc:
            logger.debug("keyring get failed for '%s': %s: %s", path, type(exc).__name__, exc)
            # Fall back to settings
            return settings.get(path, default)
    else:
        # No keyring — use plaintext
        return settings.get(path, default)


def set_secret(path: str, value: str, settings: Any) -> None:
    """Set a secret value, preferring the OS keychain over settings.json."""
    if not _is_secret_path(path):
        # Not a secret — use the normal settings setter
        settings.set(path, value)
        return

    if _HAS_KEYRING:
        try:
            if value:
                _keyring.set_password(_KEYCHAIN_SERVICE, path, value)
                # Clear from settings.json (don't store plaintext + keychain)
                settings.set(path, "")
            else:
                # Empty value — delete from keychain
                try:
                    _keyring.delete_password(_KEYCHAIN_SERVICE, path)
                except _keyring.PasswordDeleteError:
                    pass  # already absent
            return
        except Exception as exc:
            logger.debug("keyring set failed for '%s': %s: %s", path, type(exc).__name__, exc)
            # Fall back to settings
            settings.set(path, value)
    else:
        # No keyring — use plaintext
        settings.set(path, value)


def is_keyring_available() -> bool:
    """Returns True if the OS keychain is available."""
    return _HAS_KEYRING


# V18.1 (B5/S3): high-level singletons-less API. Callers that don't have
# a ``Settings`` instance to pass in can use these wrappers, which resolve
# the active Settings singleton internally. Returns True if the value
# ended up in the keychain (False = stored in plaintext settings.json).
#
# V18.2.14 (B5): ``_warned_plaintext_keys`` is now also used to emit a
# traceable WARNING on EVERY plaintext store (not just the first per key)
# so the conversion log always shows which keys are insecure. The set
# still dedupes the verbose "keyring not installed" banner so it only
# prints once at startup, but each ``store_secret`` call that falls back
# to plaintext now logs a fresh traceable record.
_warned_plaintext_keys: set = set()


def store_secret(key: str, value: str) -> bool:
    """Store a secret, preferring the OS keychain over plaintext.

    Returns:
        True  — value was stored in the OS keychain.
        False — value was stored in plaintext (settings.json) because the
                keyring library isn't installed or the keychain write
                failed; a traceable WARNING is logged on EVERY such
                fallback (with ``exc_info`` so the calling code path is
                diagnosable).

    V18.2.14 (B5): Previously the plaintext-fallback WARNING only fired
    once per key (deduped via ``_warned_plaintext_keys``). That made it
    impossible to tell from the log *when* or *how often* a key was stored
    insecurely — only that it had happened at least once. Now the dedup
    only applies to the startup banner; every ``store_secret`` plaintext
    fallback emits a fresh WARNING with the key name + a traceback so the
    calling code path is identifiable.
    """
    if not value:
        # Refuse to store empty values — no-op.
        return False
    if not _is_secret_path(key):
        # Non-secret settings path — route through Settings.set() directly
        # so we don't pollute the keychain with non-secret values.
        try:
            from utils.settings import Settings
            Settings().set(key, value)
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "store_secret: non-secret Settings.set failed for '%s': "
                "%s: %s", key, type(exc).__name__, exc, exc_info=True,
            )
        return False
    if not _HAS_KEYRING:
        # No keyring — store in plaintext and warn on EVERY call (with a
        # traceback so the calling code path is traceable). The banner-style
        # one-time warning at module import already told the user keyring is
        # missing; these per-call WARNINGs ensure the conversion log shows
        # exactly which keys were stored insecurely and when.
        logger.warning(
            "[security] API key stored in PLAINTEXT (keyring unavailable): "
            "%s — install 'keyring' to secure", key, exc_info=True,
        )
        _warned_plaintext_keys.add(key)
        try:
            from utils.settings import Settings
            set_secret(key, value, Settings())
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "store_secret: plaintext fallback failed for '%s': "
                "%s: %s", key, type(exc).__name__, exc, exc_info=True,
            )
        return False
    # Keyring available — store via keyring (existing set_secret handles the
    # plaintext clearing + storage).
    try:
        from utils.settings import Settings
        set_secret(key, value, Settings())
        return True
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning(
            "[security] store_secret: keyring set failed for '%s' (%s: %s) "
            "— falling back to PLAINTEXT", key, type(exc).__name__, exc,
            exc_info=True,
        )
        # Last-resort: store in plaintext so the user's key isn't lost.
        try:
            from utils.settings import Settings
            Settings().set(key, value)
        except Exception:
            logger.error(
                "store_secret: BOTH keyring AND plaintext failed for '%s' "
                "— key was NOT stored", key, exc_info=True,
            )
        return False


def load_secret(key: str) -> str | None:
    """Load a secret, preferring the OS keychain over settings.json.

    Returns None if the secret is not found in either store.
    """
    try:
        from utils.settings import Settings
        return get_secret(key, Settings(), default=None) or None
    except Exception as exc:  # pragma: no cover — best-effort
        logger.debug("load_secret: lookup failed for '%s': %s", key, exc)
        return None


def migrate_all_secrets(settings: Any) -> int:
    """Migrate all plaintext secrets from settings.json to the keychain.

    Returns the number of keys migrated.  Called on app startup (best-effort).
    """
    if not _HAS_KEYRING:
        return 0
    migrated = 0
    for path in _SECRET_PATHS:
        try:
            plaintext = settings.get(path, "")
            if plaintext:
                _keyring.set_password(_KEYCHAIN_SERVICE, path, plaintext)
                settings.set(path, "")
                migrated += 1
                logger.info("Migrated '%s' to OS keychain.", path)
        except Exception as exc:
            logger.debug("migration failed for '%s': %s: %s", path, type(exc).__name__, exc)
    if migrated > 0:
        logger.info("Migrated %d API key(s) from settings.json to OS keychain.", migrated)
    return migrated


__all__ = [
    "get_secret",
    "set_secret",
    "is_keyring_available",
    "migrate_all_secrets",
    "store_secret",
    "load_secret",
]
