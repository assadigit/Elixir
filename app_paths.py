"""V0.6.63: frozen-aware path resolution — the two path concerns of the
packaged app in one small module.

Why this exists
---------------
When Elixir runs from source (``python main.py``) every relative path in the
codebase resolves against the repo checkout, exactly as it always has. When
Elixir runs as a PyInstaller bundle (``Elixir.exe`` from the Windows
installer) two things change:

1. Read-only bundled resources (``prompts/``, ``assets/``, ``config/``,
   ``VERSION``, ``utils/patterns.json``, the postchecks lexicon, the tiktoken
   encoding) live under PyInstaller's bundle dir (``sys._MEIPASS`` — the
   ``_internal`` folder of a one-dir build), NOT next to the source files.
2. User data (settings, caches, logs, models, prompts mirror) must NEVER be
   written inside the install folder — it goes to ``%LOCALAPPDATA%\\Elixir``.

The two helpers below encode exactly those two rules. ``utils.settings.
user_data_dir()`` (the app's single choke point for user data) delegates to
``user_data_path()`` here and keeps its migration logic; the resource-reading
call sites use ``resource_path()`` so they work identically in source and
frozen mode.

Source-mode behavior is byte-for-byte unchanged: ``resource_path()`` anchors
at the repo root and ``user_data_path()`` returns ``~/.elixir``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Frozen user-data directory name under %LOCALAPPDATA% (Windows installer
# contract — build_installer.py and installer/Elixir.iss rely on this name).
FROZEN_USER_DIR_NAME = "Elixir"


def is_frozen() -> bool:
    """True when running as a PyInstaller bundle (Elixir.exe)."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Root of the read-only bundled resources.

    Frozen one-dir build: ``sys._MEIPASS`` (``<install>\\_internal``), with a
    defensive fallback to the exe's own folder. Source checkout: the repo
    root (the directory containing this file and ``main.py``).
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Absolute path of a read-only bundled resource.

    ``resource_path("prompts")`` → ``<repo>/prompts`` from source,
    ``<bundle>/prompts`` in the installed app. Callers must treat the result
    as read-only when frozen (the install folder is not writable data space).
    """
    return bundle_dir().joinpath(*parts)


def user_data_path(*parts: str) -> Path:
    """Absolute path inside the user-writable data directory.

    Frozen install: ``%LOCALAPPDATA%\\Elixir`` (per the installer contract —
    nothing is ever written inside the install folder). Source checkout:
    ``~/.elixir`` — identical to every previous version of Elixir.

    Migration of an existing ``~/.elixir`` into the frozen location is owned
    by ``utils.settings.user_data_dir()`` (one-time, copy-based, so a source
    checkout on the same machine keeps working unchanged).
    """
    if is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        base = Path(local_app_data) / FROZEN_USER_DIR_NAME
    else:
        base = Path.home() / ".elixir"
    return base.joinpath(*parts) if parts else base
