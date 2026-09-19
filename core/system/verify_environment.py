"""V18.3 (Phase 1.7): Launch-time verification of system-level dependencies.

Elixir depends on two Windows system-level tools that are NOT pip
packages and cannot be auto-installed:

  1. **Tesseract-OCR** — used by ``pytesseract`` for OCR on scanned PDFs.
     Installed to ``C:\\Program Files\\Tesseract-OCR`` by default.
  2. **Poppler** — used by ``pdf2image`` for PDF→image rasterization.
     Must be downloaded separately and its ``bin`` folder added to PATH
     (or configured via ``settings.paths.poppler``).

Before V18.3, a missing Poppler caused a cryptic ``pdf2image`` error
mid-conversion — the user would wait ~2 minutes for OCR to start, then get
an unintelligible traceback. This module catches the problem at LAUNCH
time and surfaces a clear, actionable error.

Usage::

    from core.system.verify_environment import verify_system_dependencies

    issues = verify_system_dependencies()
    if issues:
        for issue in issues:
            logger.warning("⚠️ %s: %s", issue.title, issue.detail)
            logger.info("   Fix: %s", issue.fix)

    (Phase 2 / task 2.4 log hygiene: the example used ``print`` — callers
    should go through :mod:`logging`, never bare ``print``.)

The function returns a list of ``DependencyIssue`` objects (empty list = all
OK). It is safe to call multiple times (no side effects). It never raises —
a broken check returns a DependencyIssue rather than crashing the launch.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "DependencyIssue",
    "verify_system_dependencies",
    "check_tesseract",
    "check_poppler",
]


@dataclass
class DependencyIssue:
    """A single system-dependency problem found at launch."""

    title: str
    detail: str
    fix: str
    severity: str = "error"  # "error" (blocks conversion) or "warning"


def _check_path_env(name: str) -> str | None:
    """Return the full path to ``name`` if it's on PATH, else None."""
    return shutil.which(name)


def _check_settings_poppler() -> str | None:
    """Check if the user configured a Poppler path in settings.

    Reads ``settings.paths.poppler`` — if set and the ``bin`` folder
    exists, returns the bin path. Otherwise None.
    """
    try:
        from utils.settings import Settings

        poppler_dir = Settings().get("paths.poppler", "")
        if not poppler_dir:
            return None
        # The setting should point to the poppler dir; bin is a subdir.
        bin_dir = Path(poppler_dir) / "bin"
        if bin_dir.is_dir():
            return str(bin_dir)
        # Or the setting might already point to bin.
        if Path(poppler_dir).is_dir() and (Path(poppler_dir) / "pdftoppm.exe").exists():
            return str(poppler_dir)
        return None
    except Exception:
        return None


def check_tesseract() -> DependencyIssue | None:
    """Verify Tesseract-OCR is installed and on PATH.

    Tesseract is required for OCR on scanned PDFs (the ``pytesseract``
    wrapper calls the ``tesseract`` binary). On Windows, the user must
    install it manually from
    https://github.com/UB-Mannheim/tesseract/wiki
    """
    tesseract_path = _check_path_env("tesseract")
    if tesseract_path:
        logger.debug("Tesseract found: %s", tesseract_path)
        return None

    # On Windows, check the default install location.
    if os.name == "nt":
        default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if default.exists():
            logger.warning(
                "Tesseract found at %s but NOT on PATH. Add it to PATH "
                "or set tesseract_cmd in settings.",
                default,
            )
            return DependencyIssue(
                title="Tesseract installed but not on PATH",
                detail=f"Tesseract found at {default} but the 'tesseract' command is not on PATH.",
                fix=f"Add {default.parent} to your PATH, or set paths.tesseract in settings.",
                severity="warning",
            )

    return DependencyIssue(
        title="Tesseract-OCR not installed",
        detail=("The 'tesseract' command was not found on PATH. OCR on scanned PDFs will fail."),
        fix=(
            "Install Tesseract-OCR from "
            "https://github.com/UB-Mannheim/tesseract/wiki "
            "(default: C:\\Program Files\\Tesseract-OCR). During install, "
            "tick the language data for the languages you need."
        ),
    )


def check_poppler() -> DependencyIssue | None:
    """Verify Poppler is installed and accessible.

    Poppler is required by ``pdf2image`` for PDF→image rasterization
    (the OCR pipeline rasterizes scanned PDFs before Tesseract). On
    Windows, the user must download it from
    https://github.com/oschwartz10612/poppler-windows/releases
    and set ``paths.poppler`` in settings to the extracted folder.
    """
    # Check if pdftoppm (the Poppler binary pdf2image calls) is on PATH.
    pdftoppm_path = _check_path_env("pdftoppm")
    if pdftoppm_path:
        logger.debug("Poppler (pdftoppm) found: %s", pdftoppm_path)
        return None

    # Check the settings-configured path.
    settings_bin = _check_settings_poppler()
    if settings_bin:
        logger.debug("Poppler found via settings.paths.poppler: %s", settings_bin)
        return None

    return DependencyIssue(
        title="Poppler not installed or not configured",
        detail=(
            "The 'pdftoppm' command (Poppler) was not found on PATH and "
            "settings.paths.poppler is not set. PDF→image rasterization "
            "will fail (OCR on scanned PDFs won't work)."
        ),
        fix=(
            "Download Poppler for Windows from "
            "https://github.com/oschwartz10612/poppler-windows/releases, "
            "extract it, and set paths.poppler in "
            "~/.elixir/settings.json to the extracted folder "
            "(the one containing the 'bin' subfolder)."
        ),
    )


def check_ollama() -> DependencyIssue | None:
    """Verify Ollama is installed and reachable.

    Ollama is the LLM runtime. This is a soft check — the app has an
    OllamaSupervisor that can restart Ollama, so we only warn if it's
    not on PATH (the user might start it manually).
    """
    ollama_path = _check_path_env("ollama")
    if ollama_path:
        return None
    return DependencyIssue(
        title="Ollama not on PATH",
        detail="The 'ollama' command was not found on PATH.",
        fix="Install Ollama from https://ollama.com and ensure it's on PATH.",
        severity="warning",
    )


def verify_system_dependencies() -> list[DependencyIssue]:
    """Run all system-dependency checks. Returns a list of issues (empty = OK).

    This is the main entry point. Call it at launch (after the UI loads,
    before the user starts a conversion). Surface each issue in a dialog
    or the status bar. Never raises — a broken check returns an issue.
    """
    issues: list[DependencyIssue] = []
    for checker in (check_tesseract, check_poppler, check_ollama):
        try:
            issue = checker()
            if issue:
                issues.append(issue)
        except Exception as exc:
            # A broken check shouldn't crash the launch.
            logger.debug("System check %s failed: %s", checker.__name__, exc)
            issues.append(
                DependencyIssue(
                    title=f"Check failed: {checker.__name__}",
                    detail=f"The {checker.__name__} check raised {type(exc).__name__}: {exc}",
                    fix="Report this — the check itself has a bug.",
                    severity="warning",
                )
            )
    return issues
