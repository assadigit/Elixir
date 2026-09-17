"""V4.7.3: VRAM manager — detect GPU memory, manage Ollama models, auto-fallback.

Solves the "NeuTTS codec fails because Ollama is hogging VRAM" problem by:
1. Detecting total/free VRAM via PyTorch
2. Listing loaded Ollama models (via /api/ps)
3. Unloading Ollama models before TTS (frees VRAM for the codec)
4. Falling back NeuTTS → Kokoro when VRAM is insufficient

Also: the normalizer's Ollama calls timeout when Ollama is busy. This
manager coordinates the sequence: unload models → run TTS → (normalizer
runs before TTS, so Ollama is still available at that point).
"""

from __future__ import annotations

import logging

from core.tts.engine import LogFn
# V18.20.4.11 (P3 / O-c5): pooled LLM transport (canonical URL resolver
# unchanged — see the W-c9 source pins in test_v182043_p2_settings_integrity).
from utils.network import session_for_url

# Approximate VRAM needed by each TTS engine's GPU component.
# NeuTTS codec: ~1.5 GB. Kokoro model: ~0.5 GB. Piper: 0 (CPU binary).

logger = logging.getLogger(__name__)

NEUTTS_CODEC_VRAM_MB = 1500
KOKORO_VRAM_MB = 500
# Safety margin — don't use more than 85% of free VRAM.
VRAM_SAFETY_MARGIN = 0.85


def _ollama_base_url() -> str:
    """V18.20.4.3 (P2 / W-c9): canonical Ollama URL (lazy — resolved per
    call, never at import time; falls back to localhost if Settings is
    unavailable). Replaces the two hardcoded ``http://localhost:11434``
    requests below, which split behavior on remote-Ollama rigs.
    """
    try:
        from utils.settings import Settings
        return Settings().get_ollama_url()
    except Exception:
        return "http://localhost:11434"


class VRAMManager:
    """Detects VRAM, manages Ollama models, advises on engine selection."""

    def __init__(self, log_callback: LogFn | None = None) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)

    # ── VRAM detection ────────────────────────────────────────────────────

    @staticmethod
    def get_vram_info() -> dict[str, int] | None:
        """Return VRAM info in MB: {total, allocated, reserved, free}.

        Returns None if CUDA is not available.
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return None
            total = torch.cuda.get_device_properties(0).total_memory
            allocated = torch.cuda.memory_allocated(0)
            reserved = torch.cuda.memory_reserved(0)
            # "Free" = total - currently allocated by any process (approx)
            # torch.cuda.mem_get_info returns (free, total) at the driver level
            free, total_driver = torch.cuda.mem_get_info(0)
            return {
                "total_mb": total // (1024 * 1024),
                "free_mb": free // (1024 * 1024),
                "allocated_mb": allocated // (1024 * 1024),
                "reserved_mb": reserved // (1024 * 1024),
            }
        except Exception as _e:
            return None

    def has_enough_vram(self, required_mb: int) -> bool:
        """Check if there's enough free VRAM for the given requirement."""
        info = self.get_vram_info()
        if info is None:
            self.log("  ⚠️ CUDA not available for VRAM check", "DEBUG")
            return False
        available = int(info["free_mb"] * VRAM_SAFETY_MARGIN)
        ok = available >= required_mb
        self.log(
            f"  💾 VRAM: {info['free_mb']} MB free / {info['total_mb']} MB total "
            f"— need {required_mb} MB → {'OK' if ok else 'INSUFFICIENT'}",
            "DEBUG"
        )
        return ok

    # ── Ollama model management ───────────────────────────────────────────

    def list_loaded_ollama_models(self) -> list[str]:
        """List currently-loaded Ollama models via /api/ps.

        Returns a list of model names. Empty if Ollama is not running.
        """
        try:
            # V18.20.4.11 (P3 / O-c5): pooled transport; canonical URL kept.
            _ps_url = f"{_ollama_base_url()}/api/ps"
            resp = session_for_url(_ps_url).get(_ps_url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return []

    def unload_ollama_models(self, except_models: list[str] | None = None) -> int:
        """Unload all Ollama models from VRAM to free memory for TTS.

        Args:
            except_models: model names to keep loaded (skip unloading these)

        Returns the number of models unloaded.
        """
        loaded = self.list_loaded_ollama_models()
        if not loaded:
            self.log("  ℹ️ No Ollama models currently loaded", "DEBUG")
            return 0

        except_set = set(except_models or [])
        unloaded = 0
        for model in loaded:
            if model in except_set:
                continue
            try:
                self.log(f"  🧹 Unloading Ollama model: {model}", "INFO")
                # Ollama doesn't have a direct "unload" API, but sending
                # a generate request with keep_alive=0 unloads the model.
                resp = session_for_url(_ollama_base_url()).post(
                    f"{_ollama_base_url()}/api/generate",
                    json={
                        "model": model,
                        "prompt": "",
                        "stream": False,
                        "keep_alive": 0,  # unload immediately
                    },
                    timeout=30,
                )
                unloaded += 1
            except Exception as e:
                self.log(f"  ⚠️ Could not unload {model}: {e}", "DEBUG")

        if unloaded > 0:
            self.log(
                f"  ✅ Unloaded {unloaded} Ollama model(s) — VRAM freed for TTS",
                "INFO"
            )
        return unloaded

    # ── Engine selection logic ────────────────────────────────────────────

    def resolve_en_engine(
        self,
        preferred: str,
        neutts_gguf_path: str | None = None,
        neutts_project_path: str | None = None,
    ) -> str:
        """Resolve which English TTS engine to actually use.

        V4.7.9: CHANGED BEHAVIOR — if the GGUF file exists, always try
        NeuTTS. The VRAM check is unreliable in background threads (PyTorch
        CUDA contexts are per-thread). Instead of blocking NeuTTS based on
        a possibly-wrong VRAM reading, we let it try — if it fails during
        inference, the engine's error handler catches it and the segment
        falls through.

        We still unload Ollama models (that's always safe) and log the
        VRAM info for diagnostics, but we don't gate on it.
        """
        if preferred != "neutts":
            return preferred

        # Unload Ollama models to free VRAM (always safe to do)
        self.log("  🔧 Preparing VRAM for NeuTTS-Air…", "INFO")
        self.unload_ollama_models()

        # Log VRAM info for diagnostics (but don't block on it)
        info = self.get_vram_info()
        if info:
            self.log(
                f"  💾 VRAM: {info['free_mb']} MB free / {info['total_mb']} MB total",
                "INFO"
            )
        else:
            self.log(
                "  💾 VRAM check unavailable (likely background thread) — "
                "proceeding with NeuTTS anyway",
                "INFO"
            )

        # Check if NeuTTS files exist
        from pathlib import Path
        if neutts_gguf_path and Path(neutts_gguf_path).exists():
            self.log("  ✅ NeuTTS-Air GGUF found — proceeding with NeuTTS", "INFO")
            return "neutts"
        else:
            self.log(
                "  ⚠️ NeuTTS GGUF model not found — falling back to Kokoro",
                "WARNING"
            )
            return "kokoro"
