"""Dependency checker with caching and model type classification — proxy disabled."""

import subprocess
import time
from typing import Any

import requests

from core.llm.model_taxonomy import is_vision_model
from core.system.timeouts import UI_PROBE_TIMEOUT_S
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
            resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=UI_PROBE_TIMEOUT_S)
            return resp.status_code == 200
        except (ConnectionError, TimeoutError, OSError):
            return False

    def check_all(self) -> dict[str, Any]:
        deps = {
            "markitdown": False,
            "tesseract": False,
            "ollama": False,
            "ollama_running": False,
            "models": [],
            "vision_models": [],
            "text_models": [],
            "markdowncleaner": False,
            "wordninja": False,
            "python_docx": False,
            "pdf2image": False,
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
                resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=UI_PROBE_TIMEOUT_S)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    deps["models"] = models
                    # V0.6.7 (review-loop B4): the vision/text split routes
                    # through model_taxonomy.is_vision_model — the SSOT union
                    # of the 3 keyword variants that had drifted apart (a
                    # minicpm-v used to classify TEXT here while the OCR
                    # dialog listed it as an OCR model).
                    deps["vision_models"] = [m for m in models if is_vision_model(m)]
                    deps["text_models"] = [m for m in models if not is_vision_model(m)]
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
                resp = self._session.get(f"{self.ollama_url}/api/tags", timeout=UI_PROBE_TIMEOUT_S)
                if resp.status_code == 200:
                    return [m["name"] for m in resp.json().get("models", [])]
            except Exception as e:
                logger.warning(f"Failed to fetch models: {e}")
            return []

        all_models = self._get_cached("ollama_models", fetch)
        # V0.6.7 (review-loop B4): same SSOT split as check_all above.
        if model_type == "vision":
            return [m for m in all_models if is_vision_model(m)]
        elif model_type == "text":
            return [m for m in all_models if not is_vision_model(m)]
        return all_models

    def model_exists(self, model_name: str) -> bool:
        return model_name in self.get_ollama_models()
