"""
Model lifecycle manager for Ollama models.
HDD-friendly (600s timeout) with proxy-proof networking.

FIXES:
  - model_exists now tries a direct /api/generate call if the model is not in the cached tags list.
  - Improved logging to show available models when a requested model is not found.
  - get_vram_usage() – returns total, used, free VRAM in GB.
  - ensure_vram_for_model() – checks free VRAM and unloads non‑critical models if needed.
  - Model type tracking (OCR, SUMMARISATION, SEMANTIC) to intelligently decide which models to offload.
  - acquire_model() now accepts skip_vram_check to bypass VRAM detection for OCR.
  - NEW: status_callback parameter to notify UI during VRAM offloading and model loading.
"""

import threading
from collections.abc import Callable
from enum import StrEnum
from typing import Optional

from core.system.timeouts import CLI_POLL_TIMEOUT_S, LONG_RUN_TIMEOUT_S
from utils.logging import get_main_logger
from utils.network import is_ollama_reachable, list_ollama_models, safe_ollama_request
from utils.settings import Settings

logger = get_main_logger()


class ModelType(StrEnum):
    OCR = "ocr"
    SUMMARISATION = "summarisation"
    SEMANTIC = "semantic"


class ModelManager:
    _instance: Optional["ModelManager"] = None
    _ollama_base_url: str = "http://localhost:11434"

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        self._settings = Settings()
        self._lock = threading.RLock()
        self._loaded_models: dict[str, int] = {}
        self._model_type_map: dict[str, ModelType] = {}
        self._unload_timers: dict[str, threading.Timer] = {}
        self._default_keep_alive = 60

    # ─────────────────────────────────────────────────────────────────────────
    # VRAM Utilities
    # ─────────────────────────────────────────────────────────────────────────

    def get_vram_usage(self) -> dict[str, float]:
        """
        Return total, used, free VRAM in GB.
        If torch is not available or no GPU, returns zeros.
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return {"total": 0.0, "used": 0.0, "free": 0.0}
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            used = torch.cuda.memory_allocated(0) / (1024**3)
            free = total - used
            return {"total": total, "used": used, "free": free}
        except ImportError:
            return {"total": 0.0, "used": 0.0, "free": 0.0}
        except Exception as e:
            logger.debug(f"VRAM detection failed: {e}")
            return {"total": 0.0, "used": 0.0, "free": 0.0}

    def ensure_vram_for_model(
        self,
        model_name: str,
        required_gb: float = 6.0,
        status_callback: Callable[[str], None] | None = None,
    ) -> bool:
        """
        Ensure at least required_gb GB of free VRAM for the given model.
        If not enough, try to unload non‑critical models (e.g., summarisation).
        Returns True if enough VRAM is available after cleanup, False otherwise.

        status_callback: optional function to update UI with progress messages.
        """
        # First, check current VRAM
        vram = self.get_vram_usage()
        if vram["free"] >= required_gb:
            logger.debug(f"VRAM sufficient: {vram['free']:.2f} GB free (need {required_gb:.2f} GB)")
            return True

        logger.info(
            f"VRAM low: {vram['free']:.2f} GB free, need {required_gb:.2f} GB. Attempting to free memory..."
        )
        if status_callback:
            status_callback(f"VRAM low – offloading models to free {required_gb:.1f} GB...")

        # List models currently loaded
        loaded = self._loaded_models.copy()
        # Sort models: prefer to unload summarisation and semantic models first,
        # keep OCR models if possible (unless they are not the one we want)
        priority = []
        for name, count in loaded.items():
            if count == 0:
                continue
            if name == model_name:
                continue  # never unload the model we need
            mtype = self._model_type_map.get(name)
            if mtype == ModelType.SUMMARISATION:
                priority.append((0, name))
            elif mtype == ModelType.SEMANTIC:
                priority.append((1, name))
            else:
                priority.append((2, name))  # OCR or unknown

        # Sort by priority
        priority.sort(key=lambda x: x[0])

        for _, name in priority:
            logger.info(f"  Force‑unloading '{name}' to free VRAM...")
            if status_callback:
                status_callback(f"Unloading {name}...")
            self.force_unload(name)
            # Check VRAM after each unload
            vram = self.get_vram_usage()
            if vram["free"] >= required_gb:
                logger.info(f"VRAM now sufficient: {vram['free']:.2f} GB free")
                if status_callback:
                    status_callback("VRAM sufficient – loading model...")
                return True

        # If we still don't have enough VRAM, log a warning
        logger.warning(
            f"Could not free enough VRAM. Available: {vram['free']:.2f} GB, need: {required_gb:.2f} GB"
        )
        if status_callback:
            status_callback(f"⚠️ Could not free enough VRAM (only {vram['free']:.2f} GB available).")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Existing methods
    # ─────────────────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return is_ollama_reachable(self._ollama_base_url)

    def list_models(self) -> list[str]:
        return list_ollama_models(self._ollama_base_url)

    def model_exists(self, model_name: str) -> bool:
        """Check if a model exists in Ollama, with fallback to a direct test."""
        available = self.list_models()
        # Case-insensitive exact match first
        for avail in available:
            if avail.lower() == model_name.lower():
                return True
        # If not found in tags, try a direct /api/generate with a short prompt
        try:
            url = f"{self._ollama_base_url}/api/generate"
            payload = {
                "model": model_name,
                "prompt": "Hello",
                "stream": False,
                "options": {"num_predict": 1},
            }
            resp = safe_ollama_request(
                "POST", url, json=payload, timeout=CLI_POLL_TIMEOUT_S, retries=0
            )
            if resp.status_code == 200:
                logger.info(f"Model '{model_name}' verified via /api/generate (not in tags list).")
                return True
        except Exception as e:
            logger.debug(f"Model '{model_name}' direct test failed: {e}")

        logger.warning(f"Model '{model_name}' not found. Available models: {available}")
        return False

    def _send_generate_request(self, model: str, prompt: str = "Hello") -> bool:
        url = f"{self._ollama_base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 1, "temperature": 0.0},
        }
        try:
            logger.info(f"Loading model {model} (may take several minutes on HDD)...")
            resp = safe_ollama_request(
                "POST", url, json=payload, timeout=LONG_RUN_TIMEOUT_S, retries=1
            )
            if resp.status_code == 200:
                logger.info(f"Model {model} loaded successfully.")
                return True
            logger.error(f"Load failed: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Exception loading model {model}: {e}")
            return False

    def _unload_model(self, model_name: str) -> bool:
        url = f"{self._ollama_base_url}/api/generate"
        payload = {
            "model": model_name,
            "prompt": "",
            "stream": False,
            "options": {"keep_alive": 0},
        }
        try:
            safe_ollama_request("POST", url, json=payload, timeout=CLI_POLL_TIMEOUT_S)
            logger.info(f"Unloaded model: {model_name}")
            return True
        except Exception as e:
            logger.warning(f"Error unloading {model_name}: {e}")
            return False

    def _schedule_unload(self, model_name: str, delay: int = None):
        if model_name in self._unload_timers:
            self._unload_timers[model_name].cancel()
        if delay is None:
            delay = self._default_keep_alive
        timer = threading.Timer(delay, self._release_model_after_timeout, args=[model_name])
        self._unload_timers[model_name] = timer
        timer.start()

    def _release_model_after_timeout(self, model_name: str):
        # V9.0.0: pop bookkeeping under the lock, HTTP call outside (P2-3)
        should_unload = False
        with self._lock:
            if self._loaded_models.get(model_name, 0) == 0:
                self._unload_timers.pop(model_name, None)
                self._loaded_models.pop(model_name, None)
                self._model_type_map.pop(model_name, None)
                should_unload = True
        if should_unload:
            self._unload_model(model_name)

    # ── MODIFIED: Added skip_vram_check and status_callback ────────────────

    def acquire_model(
        self,
        model_name: str,
        model_type: ModelType,
        skip_vram_check: bool = False,
        status_callback: Callable[[str], None] | None = None,
    ) -> bool:
        if not self.is_running():
            logger.error("Ollama server not running.")
            if status_callback:
                status_callback("❌ Ollama server not running.")
            return False
        if not self.model_exists(model_name):
            logger.error(f"Model '{model_name}' not found. Run: ollama pull {model_name}")
            if status_callback:
                status_callback(f"❌ Model '{model_name}' not found. Please pull it first.")
            return False
        with self._lock:
            if model_name in self._unload_timers:
                self._unload_timers[model_name].cancel()
                del self._unload_timers[model_name]
            count = self._loaded_models.get(model_name, 0)
            if count == 0:
                # ── Only check VRAM if not skipped ──────────────────────────
                if not skip_vram_check:
                    required = 7.0 if model_type == ModelType.OCR else 5.0
                    if not self.ensure_vram_for_model(
                        model_name, required_gb=required, status_callback=status_callback
                    ):
                        logger.error(
                            f"Not enough VRAM to load {model_name} (need ~{required:.1f} GB)."
                        )
                        if status_callback:
                            status_callback(f"❌ Not enough VRAM to load {model_name}.")
                        return False
                logger.info(f"Loading model: {model_name} (type={model_type.value})")
                if status_callback:
                    status_callback(f"⏳ Loading {model_name}...")
                if not self._send_generate_request(model_name):
                    if status_callback:
                        status_callback(f"❌ Failed to load {model_name}.")
                    return False
                self._loaded_models[model_name] = 1
                self._model_type_map[model_name] = model_type
                if status_callback:
                    status_callback(f"✅ {model_name} loaded.")
            else:
                self._loaded_models[model_name] = count + 1
                if status_callback:
                    status_callback(f"✅ {model_name} already loaded.")
            return True

    def release_model(self, model_name: str) -> bool:
        with self._lock:
            count = self._loaded_models.get(model_name, 0)
            if count == 0:
                logger.warning(f"Release called on {model_name} with zero references")
                return False
            new_count = count - 1
            self._loaded_models[model_name] = new_count
            if new_count == 0:
                logger.info(f"Last reference released for {model_name}, scheduling unload")
                self._schedule_unload(model_name)
            return True

    def force_unload(self, model_name: str) -> bool:
        # V9.0.0: pop bookkeeping under the lock, but do the HTTP unload
        # call OUTSIDE the lock — prevents up to 10s of blocking for all
        # other model operations (P2-3).
        with self._lock:
            if model_name in self._unload_timers:
                self._unload_timers[model_name].cancel()
                del self._unload_timers[model_name]
            self._loaded_models.pop(model_name, None)
            self._model_type_map.pop(model_name, None)
        # HTTP call outside the lock
        return self._unload_model(model_name)

    def get_loaded_models(self) -> dict[str, int]:
        with self._lock:
            return self._loaded_models.copy()

    def set_default_keep_alive(self, seconds: int) -> None:
        self._default_keep_alive = seconds

    # ─────────────────────────────────────────────────────────────────────────
    # V7.5.0: Proactive phase-boundary unloading
    # ─────────────────────────────────────────────────────────────────────────

    def unload_all_ollama(
        self,
        keep_models: list[str] | None = None,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> int:
        """Force-unload every tracked Ollama model except those in ``keep_models``.

        Called at phase boundaries (e.g. before translation, before TTS) to
        proactively free VRAM rather than waiting for a reactive OOM.  Returns
        the number of models unloaded.  Safe to call when nothing is loaded.
        """
        log = log_callback or (lambda msg, level="INFO": None)
        keep = set(keep_models or [])
        with self._lock:
            loaded = list(self._loaded_models.keys())
        if not loaded:
            return 0
        unloaded = 0
        for name in loaded:
            if name in keep:
                continue
            log(f"  🧹 Proactive unload: {name}", "INFO")
            if self.force_unload(name):
                unloaded += 1
        if unloaded:
            log(f"  ✅ Unloaded {unloaded} model(s) at phase boundary", "INFO")
        return unloaded

    def unload_for_translation(
        self,
        translation_backend: str,
        translation_model: str,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> int:
        """Unload models that aren't needed for the translation phase.

        Keeps the translation model (and judge/harakat if they're the same);
        unloads the summarizer + OCR.

        The legacy ``backend == "nllb"`` branch (unload EVERYTHING for the
        retired HuggingFace NLLB backend) was unreachable since V18.20.4.6+
        — core.system.bootstrap migrates ``translation.backend='nllb'`` to
        'ollama' before any read (bootstrap.py:249) — and was removed in the
        V0.4.25 Phase-4 dead-code audit.  The ``translation_backend``
        parameter is kept for call-site API compatibility (controller.py
        passes it; vram_calculator.py keeps its own NLLB-era sizing branch,
        which is similarly legacy-only).
        """
        # Ollama translation backend — keep the translator model
        return self.unload_all_ollama(
            keep_models=[translation_model] if translation_model else None,
            log_callback=log_callback,
        )
