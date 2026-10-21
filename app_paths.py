"""app_paths — frozen-aware path helpers for Elixir (source and PyInstaller).

ONE small module that answers the two path questions the app has:

1. **"Where are my read-only bundled resources?"** (prompts, fonts, VERSION,
   icons, bundled tools) — :func:`resource_path`. When the app is packed with
   PyInstaller this is the bundle folder (``sys._MEIPASS`` — ``_internal`` in
   a onedir build); when running from source it is the repository root. The
   app NEVER writes there.

2. **"Where do I put user data?"** (settings, outputs, caches, logs,
   databases) — :func:`user_data`. When frozen on Windows this is
   ``%LOCALAPPDATA%\\Elixir`` (writable for every user, survives reinstalls,
   the standard location for per-user application data); when running from
   source it is the historical ``~/.elixir`` location (unchanged).

Plus two packaging conveniences:

* :func:`setup_frozen_environment` — called once from ``main.py``; when
  frozen it prepends the bundled ``tools`` folder (ffmpeg, poppler, …) to
  ``PATH`` so every ``shutil.which()`` lookup finds the bundled copy first.
  From source it is a no-op.
* :func:`find_bundled_tool` — explicit bundle-first lookup for an external
  executable name (``ffmpeg.exe``, ``pdftoppm.exe``, …).

Import graph: this module is stdlib-only at import time (``utils.settings``
is imported lazily inside :func:`user_data`) so it can be imported from
anywhere — including from ``utils.settings`` itself — without cycles.

Running ``python main.py`` from the source tree behaves exactly as before:
every helper resolves to the historical locations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Elixir"
_LEGACY_USER_DIR_NAME = ".elixir"  # historical source-run location (do NOT rename)


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle (Elixir.exe)."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Root folder of the read-only bundled resources.

    * Frozen onedir build → ``sys._MEIPASS`` (``<install>\\Elixir\\_internal``).
    * Running from source → the repository root (folder of this file).
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
        # Defensive fallback: the executable's folder (onedir layout keeps
        # the data next to the exe when _MEIPASS is somehow unset).
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(*relative: str | os.PathLike[str]) -> Path:
    """(a) Path of a READ-ONLY bundled resource.

    ``resource_path("prompts", "default.md")`` → ``<bundle>/prompts/default.md``
    (variadic parts join like ``Path.joinpath``). Never write to the returned
    path — installed bundles live under ``Program Files``-style locations
    that may be read-only.
    """
    return bundle_dir().joinpath(*relative) if relative else bundle_dir()


def default_user_data_dir() -> Path:
    """The user-data *location* rule (pure path math, no side effects).

    * Frozen on Windows → ``%LOCALAPPDATA%\\Elixir``.
    * Everything else (incl. running from source) → ``~/.elixir``.

    The migration-aware accessor is :func:`user_data` (via
    ``utils.settings.user_data_dir``); prefer that one in app code.
    """
    if is_frozen() and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    return Path.home() / _LEGACY_USER_DIR_NAME


def user_data(relative: str | os.PathLike[str] = "") -> Path:
    """(b) Path for USER data (settings, outputs, caches, logs, databases).

    Frozen on Windows → ``%LOCALAPPDATA%\\Elixir``; from source → the
    historical ``~/.elixir``. Delegates to ``utils.settings.user_data_dir``
    so the one-time legacy-data carry-over runs exactly once. The directory
    is created on demand by the callers (settings, caches, …).
    """
    from utils.settings import user_data_dir  # lazy: avoids an import cycle

    base = user_data_dir()
    p = Path(relative) if relative else Path(".")
    return base / p


# Alias kept for the alternate call style used by some modules
# (``user_data_path()`` with no arguments).
user_data_path = user_data


def bundled_tools_dir() -> Path:
    """Folder where the installer bundles external tools (ffmpeg, poppler)."""
    return resource_path("tools")


def find_bundled_tool(name: str) -> Path | None:
    """Bundle-first lookup for an external executable.

    Checks ``<bundle>/tools/<name>`` (flat layout) and
    ``<bundle>/tools/<stem>/<name>`` (nested layout) and returns the first
    existing path, else ``None``. Callers fall back to ``shutil.which`` /
    user settings when this returns ``None``.
    """
    if not name:
        return None
    tools = bundled_tools_dir()
    candidates = [tools / name]
    stem = Path(name).stem
    if stem and stem != name:
        candidates.append(tools / stem / name)
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        exe = f"{name}.exe"
        candidates.append(tools / exe)
        if stem != exe:
            candidates.append(tools / stem / exe)
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def bundled_icon_path() -> Path | None:
    """Path of the bundled app icon (``assets/elixir.ico``), if present."""
    p = resource_path("assets") / "elixir.ico"
    try:
        return p if p.is_file() else None
    except OSError:
        return None


def setup_frozen_environment() -> None:
    """Prepare the process environment for a frozen (installed) run.

    * Prepends the bundled ``tools`` folder to ``PATH`` so
      ``shutil.which("ffmpeg")`` / ``("pdftoppm")`` find the bundled copies
      before anything on the system.
    * Redirects ``sys.stdout``/``sys.stderr`` (which are ``None`` in a
      windowed PyInstaller build) to real sinks so ``print()`` never raises
      and crash text is kept on disk.

    No-op when running from source.
    """
    if not is_frozen():
        return

    tools = bundled_tools_dir()
    try:
        if tools.is_dir():
            for entry in (tools, *(d for d in tools.iterdir() if d.is_dir())):
                entry_str = str(entry)
                path_var = os.environ.get("PATH", "")
                if entry_str not in path_var.split(os.pathsep):
                    os.environ["PATH"] = entry_str + os.pathsep + path_var
    except OSError:
        pass

    # Windowed builds: PyInstaller leaves sys.stdout/stderr as None — any
    # print() would raise AttributeError. Point them at safe sinks instead
    # (stderr → console.log in the user-data dir so crash text survives).
    try:
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    except Exception:
        sys.stdout = None  # type: ignore[assignment]
    try:
        if sys.stderr is None:
            from datetime import datetime

            log_path = user_data("console.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            sys.stderr = open(  # noqa: SIM115
                log_path, "a", encoding="utf-8", buffering=1
            )
            sys.stderr.write(f"\n=== Elixir {datetime.now().isoformat()} ===\n")
    except Exception:
        sys.stderr = None  # type: ignore[assignment]
