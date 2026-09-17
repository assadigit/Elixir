"""Dependency checker with caching and model type classification — proxy disabled."""

import subprocess
import time
from typing import Any

import requests

from utils.logging import get_main_logger

logger = get_main_logger()


class DependencyChecker:
    """Check installed dependencies, Ollama models, and system status."""

    def __init__(self, cache_ttl: float = 10.0):
        self._cache: dict[str, Any] = {}
        self._cache_time: dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self.ollama_url = "http://localhost:11434"
        self._session = requests.Session()
        self._session.trust_env = False
        self._session.proxies = {"http": None, "https": None}

    def _get_cached(self, key: str, fetcher):
        now = time.time()
        if key in self._cache and (now - self._cache_time.get(key, 0)) < self._cache_ttl:
            return self._cache[key]
        value = fetcher()
        self._cache[key] = value
        self._cache_time[key] = now
        return value

    def _is_ollama_server_running(self) -> bool:
        try:
            resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except (ConnectionError, TimeoutError, OSError):
            return False

    def check_all(self) -> dict[str, Any]:
        deps = {
            "markitdown": False, "tesseract": False, "ollama": False,
            "ollama_running": False, "models": [], "vision_models": [],
            "text_models": [], "markdowncleaner": False, "wordninja": False,
            "python_docx": False, "pdf2image": False,
        }

        try:
            import markitdown  # noqa
            deps["markitdown"] = True
        except ImportError:
            pass

        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, timeout=2)
            deps["tesseract"] = True
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        try:
            subprocess.run(["ollama", "--version"], capture_output=True, timeout=2)
            deps["ollama"] = True
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        if self._is_ollama_server_running():
            deps["ollama_running"] = True
            try:
                resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    deps["models"] = models
                    # 'ocr' (OlmOCR, DeepSeek-OCR), 'vl'/'vision' (Qwen3-VL, LLaVA),
                    # 'bakllava' — all are vision-capable OCR engines.
                    vision_keywords = ["vl", "vision", "deepseek-ocr", "llava", "bakllava", "ocr", "olmo"]
                    deps["vision_models"] = [m for m in models if any(k in m.lower() for k in vision_keywords)]
                    deps["text_models"]   = [m for m in models if not any(k in m.lower() for k in vision_keywords)]
            except Exception as e:
                logger.warning(f"Could not fetch models: {e}")

        for pkg, attr in [("markdowncleaner", "markdowncleaner"), ("wordninja", "wordninja")]:
            try:
                __import__(pkg)
                deps[attr] = True
            except ImportError:
                pass

        try:
            from docx import Document  # noqa
            deps["python_docx"] = True
        except ImportError:
            pass

        try:
            import pdf2image  # noqa
            deps["pdf2image"] = True
        except ImportError:
            pass

        return deps

    def get_ollama_models(self, model_type: str | None = None) -> list[str]:
        def fetch():
            try:
                resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    return [m["name"] for m in resp.json().get("models", [])]
            except Exception as e:
                logger.warning(f"Failed to fetch models: {e}")
            return []

        all_models = self._get_cached("ollama_models", fetch)
        vision_kw = ["vl", "vision", "deepseek-ocr", "llava", "bakllava", "ocr", "olmo"]
        if model_type == "vision":
            return [m for m in all_models if any(k in m.lower() for k in vision_kw)]
        elif model_type == "text":
            return [m for m in all_models if not any(k in m.lower() for k in vision_kw)]
        return all_models

    def model_exists(self, model_name: str) -> bool:
        return model_name in self.get_ollama_models()
