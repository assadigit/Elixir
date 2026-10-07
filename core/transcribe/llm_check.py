"""V0.6.55 (P1c): the Transcribe Service's one-click LLM health check.

WHY THIS MODULE EXISTS
──────────────────────
The Transcribe dialog had a 🔄 refresh button that LISTED models, but
no way to answer "will the summarize step actually WORK, and how FAST
will it be?" — the operator's rig spent 10+ minutes per summary with a
frozen status label before anyone noticed llama-server had fallen back
to CPU. The V0.6.54 CHANGELOG's redesign list asked for exactly this:
"a 'Test LLM connection' button" and "surface the n_gpu_layers GPU-fit
error as a clear dialog message".

WHAT IT DOES (one dict, never raises):
  1. Resolves the backend through ``decide_llamacpp_first`` — which
     since V0.6.55 (P1a) auto-detects llama.cpp's shifting ports
     (8080 → 8000 → 9931) when the setting is the unmodified default.
  2. llama.cpp live → ``probe_llamacpp_generation`` (P1b): a tiny timed
     generation whose verdict says whether the model is running at
     GPU-class speed or has fallen back to CPU (the n_gpu_layers
     GPU-fit failure) — with the actionable restart hint.
  3. No llama.cpp → the configured backend (Ollama) is probed for its
     model list; cloud selections get an honest "not probed locally"
     answer instead of a fake failure.

The returned dict carries ``save_url`` when the port was AUTO-DETECTED
on a non-default URL while the setting still holds the stale default —
the dialog persists it after showing the result (one click = fixed
for every future run; the operator is TOLD, not silently rewritten).
"""

from __future__ import annotations

import logging

from core.llm.local_fallback import LLAMACPP_DEFAULT_BASE_URL
from core.system.timeouts import UI_PROBE_TIMEOUT_S

logger = logging.getLogger(__name__)


def check_llm_for_transcribe(settings, ollama_url: str | None = None, log_callback=None) -> dict:
    """The one-click LLM health check for the Transcribe Service dialog.

    Returns a dict (never raises):
      ok        — the backend responded (a SLOW generation is ok=True
                  with level='slow-cpu-fallback-suspected' — the speed
                  is the finding, not a failure).
      level     — 'healthy' | 'slow-cpu-fallback-suspected' |
                  'unreachable' | 'info'.
      backend   — 'llama.cpp' | 'ollama' | the configured provider name.
      message   — the full user-facing text (decision note + probe
                  result — the n_gpu_layers guidance rides on the slow
                  verdict).
      save_url  — the auto-detected base URL to persist (None when the
                  configured URL was already correct/explicit).
      tps/model/base_url — the measurement details (None when not
                  probed).
    """
    log = log_callback or (lambda msg, level="INFO": None)

    provider_name = str(
        settings.get("summarisation.provider", "ollama") or "ollama"
    ).strip().lower()

    # Deferred import (the house pattern): tests monkeypatch the seam at
    # its module home, and the call-time import picks the fake up.
    from core.llm.local_fallback import decide_llamacpp_first

    decision = decide_llamacpp_first(settings, provider_name)
    if decision.use_llamacpp:
        from core.llm.llamacpp_provider import probe_llamacpp_generation

        log(f"  🔌 Probing llama.cpp at {decision.base_url} (model {decision.model})…", "INFO")
        probe = probe_llamacpp_generation(
            decision.base_url,
            decision.api_key,
            decision.model,
            log_callback=log,
        )
        # P1a interplay: offer to persist an auto-detected port — ONLY
        # when the setting still holds the unmodified default (an
        # explicit operator URL is never second-guessed).
        configured = str(
            settings.get("summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_BASE_URL)
            or LLAMACPP_DEFAULT_BASE_URL
        ).strip()
        save_url = (
            decision.base_url
            if decision.base_url != LLAMACPP_DEFAULT_BASE_URL
            and configured == LLAMACPP_DEFAULT_BASE_URL
            else None
        )
        message = decision.note.rstrip(". ")
        if save_url:
            message += f"\n\nThe port was auto-detected — clicking OK saves {save_url} as the llama.cpp URL so every future run goes straight there."
        message += f"\n\n{probe.message}"
        return {
            "ok": probe.ok,
            "level": probe.verdict,
            "backend": "llama.cpp",
            "base_url": decision.base_url,
            "model": decision.model,
            "tps": probe.tps,
            "message": message,
            "save_url": save_url,
        }

    # No live llama.cpp — the configured backend runs (the V0.6.12
    # policy: Ollama is the always-on default).
    if provider_name == "ollama":
        from utils.settings import Settings

        url = (
            ollama_url
            or (
                settings.get_ollama_url()
                if hasattr(settings, "get_ollama_url")
                else None
            )
            or settings.get("summarisation.ollama_url", "http://localhost:11434")
        )
        try:
            from utils.network import list_ollama_models

            models = [m for m in list_ollama_models(url, timeout=UI_PROBE_TIMEOUT_S) if m]
        except Exception as e:  # noqa: BLE001 — a probe failure is data, not an error
            log(f"  ⚠️ Ollama probe failed: {e}", "WARNING")
            models = []
        if models:
            shown = ", ".join(models[:5]) + ("…" if len(models) > 5 else "")
            return {
                "ok": True,
                "level": "healthy",
                "backend": "ollama",
                "base_url": url,
                "model": models[0],
                "tps": None,
                "message": (
                    f"Ollama OK at {url} — {len(models)} model(s) available: {shown}.\n"
                    f"(llama.cpp was not detected; {decision.note})"
                ),
                "save_url": None,
            }
        return {
            "ok": False,
            "level": "unreachable",
            "backend": "ollama",
            "base_url": url,
            "model": None,
            "tps": None,
            "message": (
                f"Cannot reach Ollama at {url} — start it with `ollama serve` "
                f"(or start llama-server and click Test again; ports 8080/8000/9931 "
                f"are auto-probed).\n({decision.note})"
            ),
            "save_url": None,
        }

    # A cloud / remote selection — deliberately not probed locally.
    return {
        "ok": True,
        "level": "info",
        "backend": provider_name,
        "base_url": None,
        "model": None,
        "tps": None,
        "message": (
            f"The configured summary provider is '{provider_name}' (a cloud/remote "
            f"selection) — no local probe applies. The transcript summary will use "
            f"it as configured."
        ),
        "save_url": None,
    }
