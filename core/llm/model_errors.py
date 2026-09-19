"""V18.20.4.12 (T-c7): Shared model-not-found (HTTP 404) error semantics.

Before this module, "the configured Ollama model is not pulled" was handled
THREE different ways across the tree:

  1. **Typed raise** — ``core/llm/ollama_provider.py`` (V11.17) and
     ``core/llm/async_provider.py`` raise ``ModelNotFound404Error`` (defined
     in ``core/llm/retry.py`` since V18.2.21) and the outer handler logs the
     actionable ``ollama pull`` message.
  2. **Generic WARNING → None** — ``core/outputs/packets/generator.py``
     ``_call_llm`` caught the resulting ``requests.HTTPError`` in a blanket
     ``except Exception`` and logged only the raw "404 Client Error" line
     (no pull hint — the V18.20.4.0 SWOT cited this).
  3. **Pre-emptive self-healing** — ``core/tts/normalizer.py``
     (V4.7.24) auto-discovers a model from ``/api/tags`` when the
     configured one is empty/known-bad, but an explicitly-configured
     missing model still 404ed into a generic handler.

This module unifies the **detection** and the **message** only:

  - ``ModelNotFound404Error`` — moved here from ``core/llm/retry.py``
    (constructor + message byte-identical; both modules re-export it, so
    every existing importer keeps working with zero changes).
  - ``model_not_found_hint(model)`` — THE canonical actionable message
    (matches the pre-move exception wording; tests pin ``ollama pull``).
  - ``is_model_not_found(status, text)`` — tolerant detector for call
    sites that only have a response status and/or body.

Deliberately NOT unified here (control-flow semantics stay per-site,
documented as future work): who *raises* the typed exception (providers)
vs who *returns None with a WARNING* (packets) vs who *falls back to
deterministic output* (TTS normalizer). Each site's outcome contract is
pinned by its own tests; changing raise-vs-return is a behavior change
that needs its own sign-off.

Stdlib-only imports — this module sits at the very bottom of the
``core.llm`` dependency graph so ANY module (providers, outputs, TTS,
UI dialogs) can import it without cycle risk.
"""

from __future__ import annotations

__all__ = [
    "ModelNotFound404Error",
    "model_not_found_hint",
    "is_model_not_found",
]


def model_not_found_hint(model: str) -> str:
    """The canonical actionable "model not pulled" message.

    Wording matches the pre-V18.20.4.12 ``ModelNotFound404Error`` message
    (``core/llm/retry.py``, V18.2.21) exactly — existing tests pin
    ``"ollama pull {model}"`` inside ``str(exc)`` — and the substance of
    ``OllamaProvider``'s V11.17 ERROR log lines ("Model '…' is NOT
    installed in Ollama (HTTP 404)" / "Fix: ``ollama pull …``").

    Use this everywhere a model-missing 404 needs a user-facing log line,
    so every site prints the SAME fix instruction.
    """
    return f"Model '{model}' not found in Ollama (HTTP 404) — run `ollama pull {model}`"


class ModelNotFound404Error(RuntimeError):
    """Ollama returned HTTP 404 (model not pulled). Non-retryable.

    V18.2.21: pulled out of the inline ``if status == 404: return None``
    branch in ``OllamaProvider.complete`` so the ``@retry_llm_call``
    decorator can classify it uniformly via ``classify_ollama_exception``.
    Pulling a model is a user action (``ollama pull <model>``), not a
    transient error.

    V18.20.4.12 (T-c7): moved here from ``core/llm/retry.py`` so
    non-retry-module consumers (outputs/packets, tts/normalizer, dialogs)
    can share the class + the canonical hint without importing the retry
    machinery. ``core.llm.retry`` and ``core.llm.ollama_provider``
    re-export it for backward compat. Constructor signature, attributes
    (``.model`` / ``.detail``) and message are byte-identical to the
    pre-move definition.
    """

    def __init__(self, model: str, detail: str = "") -> None:
        self.model = model
        self.detail = detail
        # Message construction kept VERBATIM from core/llm/retry.py
        # (V18.2.21): ``detail`` is spliced BEFORE the pull hint. With
        # ``detail=""`` the result equals ``model_not_found_hint(model)``
        # (pinned by tests in tests/test_v1820412_c_llm_errors.py).
        msg = f"Model '{model}' not found in Ollama (HTTP 404)"
        if detail:
            msg += f": {detail}"
        msg += f" — run `ollama pull {model}`"
        super().__init__(msg)


def is_model_not_found(status: int | None, text: str = "") -> bool:
    """Tolerant "model not found" detector for call sites without exceptions.

    Two recognition modes:

      - ``status == 404`` → True (Ollama returns 404 for an unpulled
        model on ``/api/generate`` / ``/v1/chat/completions``).
      - ``status is None`` and the response *body* mentions both
        "model" and "not found" (case-insensitive) → True — for sites
        that only have a response/error body (e.g. some OpenAI-compat
        providers return 200/500 with an error payload).

    Any other explicit status (500, 429, …) → False even if the body
    mentions "not found": when we HAVE a status code we trust it, so a
    500 "model not found" stays a generic server error for the caller's
    own handling.
    """
    if status == 404:
        return True
    if status is None:
        t = (text or "").lower()
        return "not found" in t and "model" in t
    return False
