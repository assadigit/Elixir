"""V4.7.0: Dependency checker — verifies all required/optional libraries,
engines, and system binaries are available before a conversion runs.

V13.29.0 (P3.7): Fixed logger docstring bug (was inside module docstring).
Also renamed class from DependencyChecker to DetailedDependencyChecker to
avoid collision with utils.dependencies.DependencyChecker (which has a
different API — returns dict, not List[DependencyStatus]).

Each check returns a :class:`DependencyStatus` with:
* ``name`` — display name
* ``category`` — "core" / "tts" / "binary" / "optional"
* ``ok`` — True if available, False if missing, None if optional+missing
* ``status_text`` — human-readable status ("installed", "not found", etc.)
* ``version`` — version string if available
* ``path`` — file path if relevant
* ``required`` — True if required, False if optional
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The :class:`DetailedDependencyChecker` runs all checks and returns a list of
# statuses, grouped by category. Used by the Settings → Dependencies
# dashboard to show live pulsing indicators.

import importlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ── Status dataclass ──────────────────────────────────────────────────────


@dataclass
class DependencyStatus:
    """Result of a single dependency check."""

    name: str
    category: str  # "core" / "tts" / "binary" / "optional"
    ok: bool | None  # True=ok, False=missing, None=optional+missing
    status_text: str
    version: str = ""
    path: str = ""
    required: bool = True

    @property
    def is_ok(self) -> bool:
        """True if the dependency is available (required or optional)."""
        return self.ok is True

    @property
    def is_optional_missing(self) -> bool:
        """True if optional and not installed (not an error)."""
        return self.ok is None

    @property
    def is_required_missing(self) -> bool:
        """True if required and not installed (error)."""
        return self.ok is False


# ── Checker ───────────────────────────────────────────────────────────────


class DetailedDependencyChecker:
    """V13.29.0: Renamed from DependencyChecker to avoid collision with
    utils.dependencies.DependencyChecker (which has a different API).

    This class returns List[DependencyStatus] (rich objects with category,
    version, path). The utils.dependencies.DependencyChecker returns a plain
    dict of statuses.

    Runs all dependency checks and returns grouped results.

    Usage::

        checker = DetailedDependencyChecker()
        results = checker.check_all()
        for status in results:
            logger.info("%s: %s", status.name, status.status_text)

    (Phase 2 / task 2.4 log hygiene: the example used ``print`` — callers
    should go through :mod:`logging`, never bare ``print``.)
    """

    def __init__(self) -> None:
        self._settings = None

    def _get_setting(self, key: str, default: str = "") -> str:
        """Lazy-load settings to avoid circular import."""
        if self._settings is None:
            try:
                from utils.settings import Settings

                self._settings = Settings()
            except Exception as _e:
                self._settings = {}
        if hasattr(self._settings, "get"):
            return self._settings.get(key, default)
        return default

    def check_all(self) -> list[DependencyStatus]:
        """Run all checks and return a list of statuses (grouped by category)."""
        results: list[DependencyStatus] = []
        # Core packages
        for name, import_name in [
            ("PySide6", "PySide6"),
            ("PyTorch", "torch"),
            ("Transformers", "transformers"),
            ("NumPy", "numpy"),
            ("soundfile", "soundfile"),
            ("pydub", "pydub"),
            ("HuggingFace Hub", "huggingface_hub"),
            ("pdfplumber", "pdfplumber"),
            ("spaCy", "spacy"),
            ("sentence-transformers", "sentence_transformers"),
            ("ChromaDB", "chromadb"),
            ("LangChain", "langchain"),
        ]:
            results.append(self._check_import(name, import_name, "core"))

        # TTS packages
        for name, import_name in [
            ("Kokoro", "kokoro"),
            ("Misaki (phonemizer)", "misaki"),
            ("Piper TTS", "piper"),
            ("llama-cpp-python", "llama_cpp"),
            ("phonemizer-fork", "phonemizer"),
        ]:
            results.append(self._check_import(name, import_name, "tts"))

        # System binaries
        results.append(self._check_ollama())
        results.append(self._check_piper_binary())
        results.append(self._check_ffmpeg())
        results.append(self._check_tesseract())
        results.append(self._check_poppler())

        # TTS engine configurations
        results.append(self._check_neutts_gguf())
        results.append(self._check_neutts_project())
        results.append(self._check_kokoro_model())

        # Optional
        results.append(self._check_import("pyenchant", "enchant", "optional", required=False))
        results.append(self._check_import("detectron2", "detectron2", "optional", required=False))
        results.append(self._check_import("camelot", "camelot", "optional", required=False))
        results.append(self._check_import("pymupdf (fitz)", "fitz", "optional", required=False))

        return results

    def check_category(self, category: str) -> list[DependencyStatus]:
        """Run checks for one category only."""
        return [s for s in self.check_all() if s.category == category]

    def all_required_ok(self) -> bool:
        """True if ALL required dependencies are available."""
        return all(s.is_ok for s in self.check_all() if s.required)

    # ── Individual checks ────────────────────────────────────────────────

    def _check_import(
        self,
        name: str,
        import_name: str,
        category: str,
        required: bool = True,
    ) -> DependencyStatus:
        """Check if a Python package is importable + get its version."""
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "")
            return DependencyStatus(
                name=name,
                category=category,
                ok=True,
                status_text="installed" + (f" v{version}" if version else ""),
                version=version,
                required=required,
            )
        except ImportError:
            ok = None if not required else False
            status = "not installed" + (" (optional)" if not required else "")
            return DependencyStatus(
                name=name,
                category=category,
                ok=ok,
                status_text=status,
                required=required,
            )
        except Exception as e:
            ok = None if not required else False
            return DependencyStatus(
                name=name,
                category=category,
                ok=ok,
                status_text=f"error: {e}",
                required=required,
            )

    def _check_ollama(self) -> DependencyStatus:
        """Check if Ollama is running on localhost:11434."""
        import requests

        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return DependencyStatus(
                    name="Ollama (LLM runtime)",
                    category="binary",
                    ok=True,
                    status_text=f"running ({len(models)} models)",
                    version="",
                    path="localhost:11434",
                )
            return DependencyStatus(
                name="Ollama (LLM runtime)",
                category="binary",
                ok=False,
                status_text=f"HTTP {resp.status_code}",
            )
        except Exception as _e:
            return DependencyStatus(
                name="Ollama (LLM runtime)",
                category="binary",
                ok=False,
                status_text="not running (start: ollama serve)",
            )

    def _check_piper_binary(self) -> DependencyStatus:
        """Check if the Piper binary exists."""
        path = self._get_setting(
            "tts.piper_binary",
            r"C:\piper_windows_amd64\piper\piper.exe",
        )
        p = Path(path)
        if p.exists():
            return DependencyStatus(
                name="Piper binary (Persian TTS)",
                category="binary",
                ok=True,
                status_text="found",
                path=str(p),
            )
        return DependencyStatus(
            name="Piper binary (Persian TTS)",
            category="binary",
            ok=False,
            status_text="not found",
            path=str(p),
        )

    def _check_ffmpeg(self) -> DependencyStatus:
        """Check if ffmpeg is on PATH (optional, for mp3 export)."""
        return self._check_binary(
            "ffmpeg",
            "ffmpeg",
            required=False,
            desc="FFmpeg (optional, mp3 export)",
        )

    def _check_tesseract(self) -> DependencyStatus:
        """Check if Tesseract OCR is installed (optional)."""
        return self._check_binary(
            "tesseract",
            "tesseract",
            required=False,
            desc="Tesseract OCR (optional)",
        )

    def _check_poppler(self) -> DependencyStatus:
        """Check if Poppler is available (for PDF rendering)."""
        # Try the auto-detected path from settings, or check common locations
        for name in ["pdftoppm", "pdftotext"]:
            found = shutil.which(name)
            if found:
                return DependencyStatus(
                    name="Poppler (PDF rendering)",
                    category="binary",
                    ok=True,
                    status_text="found",
                    path=found,
                )
        # Check Windows auto-detected path
        poppler_path = self._get_setting("ocr.poppler_path", "")
        if poppler_path and Path(poppler_path).exists():
            return DependencyStatus(
                name="Poppler (PDF rendering)",
                category="binary",
                ok=True,
                status_text="found (auto-detected)",
                path=poppler_path,
            )
        return DependencyStatus(
            name="Poppler (PDF rendering)",
            category="binary",
            ok=None,
            status_text="not found (optional)",
            required=False,
        )

    def _check_neutts_gguf(self) -> DependencyStatus:
        """Check if the NeuTTS-Air GGUF model file exists."""
        path = self._get_setting(
            "tts.neutts_gguf_path",
            r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
        )
        p = Path(path)
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            return DependencyStatus(
                name="NeuTTS-Air GGUF model",
                category="tts",
                ok=True,
                status_text=f"found ({size_mb:.0f} MB)",
                path=str(p),
            )
        return DependencyStatus(
            name="NeuTTS-Air GGUF model",
            category="tts",
            ok=False,
            status_text="not found",
            path=str(p),
        )

    def _check_neutts_project(self) -> DependencyStatus:
        """Check if the NeuTTS project folder exists (with neutts/ subfolder)."""
        path = self._get_setting(
            "tts.neutts_project_path",
            r"G:\Program Files\neutts-air",
        )
        p = Path(path)
        if p.exists() and (p / "neutts").is_dir():
            return DependencyStatus(
                name="NeuTTS project folder",
                category="tts",
                ok=True,
                status_text="found (neutts package present)",
                path=str(p),
            )
        return DependencyStatus(
            name="NeuTTS project folder",
            category="tts",
            ok=False,
            status_text="not found or missing neutts/ subfolder",
            path=str(p),
        )

    def _check_kokoro_model(self) -> DependencyStatus:
        """Check if the Kokoro model is cached (downloads on first use)."""
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        kokoro_cache = cache_dir / "models--hexgrad--Kokoro-82M"
        if kokoro_cache.exists():
            return DependencyStatus(
                name="Kokoro model (cached)",
                category="tts",
                ok=True,
                status_text="cached (~330 MB)",
                path=str(kokoro_cache),
            )
        return DependencyStatus(
            name="Kokoro model (cached)",
            category="tts",
            ok=None,
            status_text="not cached (downloads on first use)",
            required=False,
        )

    def _check_binary(
        self, cmd: str, name: str, required: bool = True, desc: str = ""
    ) -> DependencyStatus:
        """Check if a binary is on PATH."""
        found = shutil.which(cmd)
        if found:
            # Try to get version
            version = ""
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    version = result.stdout.strip().split("\n")[0][:60]
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return DependencyStatus(
                name=desc or name,
                category="binary",
                ok=True,
                status_text="found" + (f" ({version})" if version else ""),
                path=found,
                required=required,
            )
        ok = None if not required else False
        return DependencyStatus(
            name=desc or name,
            category="binary",
            ok=ok,
            status_text="not found" + (" (optional)" if not required else ""),
            required=required,
        )
