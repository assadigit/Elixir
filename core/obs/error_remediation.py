"""V18.2.26 (Phase 5.2) — Actionable error states for LLM failures.

The problem
-----------
When the LLM pipeline fails, the user sees a generic "Conversion FAILED"
message with no actionable guidance. The V18.2.21 conversion log showed:
- 404 (model not installed) → no `ollama pull` hint
- OOM → no "reduce context" hint
- Timeout → no "try IQ2_M quant" hint

The fix (Phase 5.2)
-------------------
A mapping from the V18.2.21 retry exception classes to user-facing
remediation messages. The UI can display these in a friendly dialog;
the backend log gets the technical detail.

Design: pure function, no deps
-----------------------------
``get_error_remediation(exc) -> RemediationInfo`` inspects the exception
type + message and returns a structured remediation. The UI maps
``RemediationInfo.severity`` to icon + color; the ``action`` field is a
button the user can click (e.g. "Open Settings" or copy the `ollama pull`
command).

Book-agnostic (Key Decision #3): error messages are structural.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RemediationInfo:
    """A user-facing remediation for an LLM error.

    Attributes:
        severity: "info" | "warning" | "error" (maps to UI icon/color).
        title: short title for the error dialog (e.g. "Model not installed").
        message: user-friendly explanation (no stack traces).
        action: optional actionable step (e.g. "Run: ollama pull gemma4-12b:latest").
        action_type: "command" (copy-paste) | "settings" (open settings) | "none".
        technical: the technical detail for the log (exception type + message).
    """

    severity: str  # "info" | "warning" | "error"
    title: str
    message: str
    action: str = ""
    action_type: str = "none"  # "command" | "settings" | "none"
    technical: str = ""


def get_error_remediation(exc: BaseException) -> RemediationInfo:
    """Map an LLM exception to a user-facing remediation.

    Inspects the exception type + message. Returns a structured
    ``RemediationInfo`` the UI can display in a friendly dialog.

    Handles the V18.2.21 retry exception classes:
    - ``ModelNotFound404Error`` → "Model not installed" + `ollama pull` hint
    - ``OllamaTimeoutError`` → "Model stalled" + "try IQ2_M quant" hint
    - ``OllamaOOMError`` → "Out of memory" + "reduce context" hint
    - ``EmbedderUnavailable`` → "Embedder model missing" + `ollama pull` hint
    - Generic ConnectionError → "Can't reach Ollama" + "is Ollama running?" hint
    - Generic Exception → fallback "Unexpected error"

    Args:
        exc: the exception that was raised.

    Returns:
        A ``RemediationInfo`` with severity, title, message, action.
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    technical = f"{exc_type}: {exc_msg[:300]}"

    # ── ModelNotFound404Error ────────────────────────────────────────────
    if exc_type == "ModelNotFound404Error":
        # Try to extract the model name for the `ollama pull` command.
        model_name = ""
        try:
            # ModelNotFound404Error has a .model attribute
            model_name = getattr(exc, "model", "") or ""
        except Exception:
            pass
        if not model_name:
            # Fallback: extract from the message
            import re

            m = re.search(r"model['\"]?\s*[:=]?\s*['\"]?([^'\"\s]+)", exc_msg, re.IGNORECASE)
            if m:
                model_name = m.group(1)
        action = f"ollama pull {model_name}" if model_name else "ollama pull <model-name>"
        return RemediationInfo(
            severity="error",
            title="Model not installed",
            message=(
                f"The model '{model_name}' is not installed in Ollama. "
                f"Elixir needs it to generate summaries."
                if model_name
                else "The configured model is not installed in Ollama."
            ),
            action=action,
            action_type="command",
            technical=technical,
        )

    # ── OllamaTimeoutError ───────────────────────────────────────────────
    if exc_type == "OllamaTimeoutError":
        return RemediationInfo(
            severity="warning",
            title="Model stalled",
            message=(
                "The model took too long to respond and was stopped. This is "
                "common with aggressive quantizations (IQ2_XXS) on complex "
                "prompts. The summary was kept, but this chapter consumed "
                "extra time."
            ),
            action=(
                "Try a less aggressive quant (IQ2_M instead of IQ2_XXS), "
                "or reduce the chapter size."
            ),
            action_type="settings",
            technical=technical,
        )

    # ── OllamaOOMError ───────────────────────────────────────────────────
    if exc_type == "OllamaOOMError":
        return RemediationInfo(
            severity="error",
            title="Out of GPU memory",
            message=(
                "Ollama ran out of GPU VRAM. The model is too large for the "
                "configured context window, or another process is using VRAM."
            ),
            action=(
                "Reduce max_context_tokens in Settings (e.g. 32768 → 16384), "
                "or close other GPU-heavy apps, or use a smaller model."
            ),
            action_type="settings",
            technical=technical,
        )

    # ── EmbedderUnavailable ──────────────────────────────────────────────
    if exc_type == "EmbedderUnavailable" or "EmbedderUnavailable" in exc_type:
        import re

        # Extract model name from the message if present
        m = re.search(r"model ['\"]([^'\"]+)['\"]", exc_msg, re.IGNORECASE)
        model_name = m.group(1) if m else "all-MiniLM-L6-v2"
        return RemediationInfo(
            severity="warning",
            title="Embedding model unavailable",
            message=(
                f"The embedding model '{model_name}' is not available. "
                f"Semantic similarity checks (coverage, dedup) will use a "
                f"weaker fallback. Summaries will still be produced."
            ),
            action=f"ollama pull {model_name}",
            action_type="command",
            technical=technical,
        )

    # ── ConnectionError (Ollama not running) ────────────────────────────
    if (
        "ConnectionError" in exc_type
        or "Connection refused" in exc_msg
        or "Connection aborted" in exc_msg
    ):
        return RemediationInfo(
            severity="error",
            title="Can't reach Ollama",
            message=(
                "Elixir can't connect to the Ollama server. The "
                "model server may not be running, or the port may be wrong."
            ),
            action="Start Ollama (run `ollama serve` or open the Ollama app).",
            action_type="command",
            technical=technical,
        )

    # ── Timeout (generic) ───────────────────────────────────────────────
    if "Timeout" in exc_type or "timed out" in exc_msg.lower():
        return RemediationInfo(
            severity="warning",
            title="Request timed out",
            message=(
                "An LLM request timed out. The model may be loading, or the "
                "request may be too large."
            ),
            action=(
                "Wait for the model to load, or reduce the chapter size, "
                "or increase the timeout in Settings."
            ),
            action_type="settings",
            technical=technical,
        )

    # ── Empty response (IQ2_XXS common) ────────────────────────────────
    if "empty response" in exc_msg.lower() or "Empty response" in exc_msg:
        return RemediationInfo(
            severity="warning",
            title="Model returned empty response",
            message=(
                "The model returned an empty response. This is common with "
                "aggressive quantizations (IQ2_XXS) at low temperatures."
            ),
            action=(
                "Raise temperature to 0.7+ in Settings, or switch to IQ2_M quant for stability."
            ),
            action_type="settings",
            technical=technical,
        )

    # ── Fallback ────────────────────────────────────────────────────────
    return RemediationInfo(
        severity="error",
        title="Unexpected error",
        message=(
            f"An unexpected error occurred: {exc_type}. Check the conversion log for details."
        ),
        action="Check the log at ~/.elixir/system.log",
        action_type="command",
        technical=technical,
    )


def format_for_log(remediation: RemediationInfo) -> str:
    """Format a RemediationInfo as a single-line log message."""
    parts = [f"[{remediation.severity.upper()}] {remediation.title}"]
    if remediation.action:
        parts.append(f"→ {remediation.action}")
    parts.append(f"({remediation.technical})")
    return " ".join(parts)
