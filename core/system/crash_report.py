"""V10.34.0 (Sprint 6.9): Crash report bundle generator.

When the app hits an unhandled exception, this module collects:
  - The full traceback
  - The current settings.json (with API keys redacted)
  - The last 200 lines of the conversion log (if available)
  - System info (Python version, OS, GPU if detectable)

...and zips them into ``~/.elixir/crash_reports/crash_YYYYMMDD_HHMMSS.zip``.

This gives the user a single file they can attach to a bug report,
instead of having to manually find + redact the log + settings.

Usage (called from main.py's excepthook)::

    from core.system.crash_report import generate_crash_report
    report_path = generate_crash_report(exc_type, exc_value, exc_tb)
    # show report_path in the error dialog
"""

from __future__ import annotations

import datetime
import json
import logging
import platform
import sys
import traceback
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_CRASH_DIR = Path.home() / ".elixir" / "crash_reports"
_SETTINGS_FILE = Path.home() / ".elixir" / "settings.json"
_LOG_FILE = Path.home() / ".elixir" / "system.log"

# Keys whose values must be redacted (never appear in the crash bundle).
# V18.1 (S4): substring match (case-insensitive) so the list catches
# every flavour of API-key-like setting without needing a hand-maintained
# enumerated set. Covers: api_key, claude_api_key, freellmapi_key,
# fusion_cloud_api_key, fast_api_key, normalize_api_key, cloud_api_key,
# translation.cloud_api_key, tts.cloud_api_key, grounding.cloud_api_key,
# any "apikey" (no underscore), tokens, secrets, passwords, auth headers.
_REDACT_KEYS = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "auth",
}

# Keys likely to hold absolute paths (and thus leak the local username).
# When such a key's value contains the user's home directory prefix, the
# prefix is replaced with ``~`` (the value is *not* fully redacted — paths
# are useful for debugging, just without the username).
_PATH_KEYS = {"path", "dir", "directory", "file", "glossary"}

# User home directory — used to scrub absolute paths so usernames don't
# leak into the crash bundle (e.g. /home/alice/.../foo → ~/.../foo).
_HOME = str(Path.home()) if Path.home() else ""


def _redact_settings(settings: dict) -> dict:
    """Return a copy of settings with all API keys / passwords redacted.

    V18.1 (S4): the redaction now also scrubs the user's home directory out
    of any ``*path*``/``*dir*``/``*glossary*`` setting value (case-insensitive
    key match) so absolute paths like ``/home/alice/.../glossary.json``
    become ``~/.../glossary.json``. Previously a crash bundle could leak
    the local username via translation.glossary, ocr.unlimited_ocr_path,
    ocr.deepseek_ocr2_path, postprocess.*_path, etc.
    """

    def _redact(obj, key_path=""):
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                k_lower = k.lower()
                if any(r in k_lower for r in _REDACT_KEYS):
                    # V18.1 (S4): never let any api_key / token / secret /
                    # password / auth value through — even an empty one
                    # is replaced so the *presence* of the field is
                    # visible without leaking its value.
                    out[k] = "***REDACTED***"
                elif any(p in k_lower for p in _PATH_KEYS) and isinstance(v, str) and v:
                    # Strip the home directory prefix so absolute paths
                    # don't leak the local username.
                    out[k] = v.replace(_HOME, "~") if _HOME else v
                else:
                    out[k] = _redact(v, k)
            return out
        elif isinstance(obj, list):
            return [_redact(item, key_path) for item in obj]
        return obj

    return _redact(settings)


def collect_recent_log_lines(max_lines: int = 200) -> list[str] | None:
    """The last ``max_lines`` of ~/.elixir/system.log (None if absent/unreadable).

    V0.6.6 (review-loop B3): shared by BOTH crash handlers. main.py has
    collected these inline since V13.29.0 (P3.8), but the controller's
    conversion-crash path never passed them — so a crash INSIDE a
    conversion produced a zip without the recent-log context the
    V13.29.0 fix existed to provide. One helper, both call sites.
    """
    try:
        if _LOG_FILE.exists():
            from collections import deque

            with open(_LOG_FILE, encoding="utf-8", errors="replace") as f:
                return list(deque(f, maxlen=max_lines))
    except Exception:
        logger.debug("could not read system.log for crash report", exc_info=True)
    return None


def _get_system_info() -> dict:
    """Collect system info for the crash report."""
    info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    # GPU info (best-effort)
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info["gpu"] = {
                "name": props.name,
                "total_vram_gb": round(props.total_memory / (1024**3), 2),
            }
        else:
            info["gpu"] = "CUDA not available"
    except ImportError:
        info["gpu"] = "torch not installed"
    except Exception as _e:
        info["gpu"] = "GPU detection failed"
    return info


def generate_crash_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb,
    extra_log_lines: list | None = None,
) -> Path | None:
    """Generate a crash report zip. Returns the path, or None on failure.

    The zip contains:
      - ``traceback.txt`` — the full exception traceback
      - ``system_info.json`` — Python/OS/GPU info
      - ``settings_redacted.json`` — settings with API keys redacted
      - ``recent_log.txt`` — the last N log lines (if provided via extra_log_lines)
    """
    try:
        _CRASH_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = _CRASH_DIR / f"crash_{timestamp}.zip"

        # Traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        # System info
        sys_info = _get_system_info()

        # Settings (redacted)
        settings_redacted = {}
        if _SETTINGS_FILE.exists():
            try:
                raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
                settings_redacted = _redact_settings(raw)
            except Exception as _e:
                settings_redacted = {"error": "could not parse settings.json"}

        # Write the zip
        with zipfile.ZipFile(report_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("traceback.txt", tb_text)
            zf.writestr("system_info.json", json.dumps(sys_info, indent=2, ensure_ascii=False))
            zf.writestr(
                "settings_redacted.json",
                json.dumps(settings_redacted, indent=2, ensure_ascii=False),
            )
            if extra_log_lines:
                zf.writestr("recent_log.txt", "\n".join(extra_log_lines))

        logger.debug("Crash report generated: %s", report_path)
        return report_path
    except Exception as exc:
        logger.error("Failed to generate crash report: %s: %s", type(exc).__name__, exc)
        return None


__all__ = ["generate_crash_report", "collect_recent_log_lines"]
