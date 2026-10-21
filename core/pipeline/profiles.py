"""V7.2.0 S23: Configuration profiles — save/load named settings profiles.

Allows users to save their current wizard settings as a named profile
(e.g., "Psychology Book", "Academic Paper") and switch between them
with one click — instead of walking through 10 wizard steps each time.

Profiles are stored in ``~/.elixir/profiles/`` as JSON files::

    {
        "name": "Psychology Book",
        "created_at": "2026-07-19T14:30:00",
        "source_type": "normal_book",
        "outputs": {...},
        "models": {...},
        "translation": {...},
        "advanced": {...}
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.settings import user_data_dir

logger = logging.getLogger(__name__)

# PACKAGING: user_data_dir() → %LOCALAPPDATA%\Elixir when frozen (installed
# build), ~/.elixir from source — behavior unchanged for source runs.
_PROFILES_DIR = user_data_dir() / "profiles"


def _ensure_dir() -> Path:
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR


def _sanitize_name(name: str) -> str:
    """Sanitize a profile name for use as a filename."""
    import re

    safe = re.sub(r'[:?*<>|"\\/]', "", name)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:60]


def save_profile(name: str, settings: dict[str, Any]) -> bool:
    """Save a named profile with the given settings."""
    try:
        safe_name = _sanitize_name(name)
        if not safe_name:
            return False
        path = _ensure_dir() / f"{safe_name}.json"
        data = {
            "name": name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "settings": settings,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False


def load_profile(name: str) -> dict[str, Any] | None:
    """Load a named profile. Returns the settings dict, or None if not found."""
    safe_name = _sanitize_name(name)
    path = _ensure_dir() / f"{safe_name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("settings", {})
    except OSError:
        return None


def list_profiles() -> list[dict[str, Any]]:
    """List all saved profiles. Returns list of {name, created_at, path} dicts."""
    profiles = []
    if not _PROFILES_DIR.exists():
        return profiles
    for f in sorted(_PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append(
                {
                    "name": data.get("name", f.stem),
                    "created_at": data.get("created_at", ""),
                    "path": str(f),
                }
            )
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
    return profiles


def delete_profile(name: str) -> bool:
    """Delete a named profile."""
    safe_name = _sanitize_name(name)
    path = _ensure_dir() / f"{safe_name}.json"
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception as _e:
            return False
    return False
