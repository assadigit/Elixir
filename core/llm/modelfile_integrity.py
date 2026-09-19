"""V18.10 (Phase 6.5): Modelfile integrity check.

On model load, run ``ollama show --modelfile <model>`` and verify the
Modelfile contains the expected parameters. For Qwen3 models, assert
``presence_penalty=1.5`` (the V18.2.41 critical fix — presence_penalty=0
causes thinking-mode leaks).

This is additive — if the check fails, a WARNING is logged but the load
proceeds (fail-open). The user can investigate.

Usage::

    from core.llm.modelfile_integrity import check_modelfile_integrity
    is_ok, issues = check_modelfile_integrity("qwen3:32b")
    if not is_ok:
        for issue in issues:
            logger.warning("Modelfile issue: %s", issue)
"""

from __future__ import annotations

import re
import subprocess

__all__ = ["check_modelfile_integrity", "parse_modelfile", "ModelfileIssue"]

# Timeout for `ollama show --modelfile` (seconds). The command is fast (<1s)
# but we set a generous timeout in case Ollama is slow to respond.
_OLLAMA_SHOW_TIMEOUT = 10


class ModelfileIssue:
    """A single Modelfile integrity issue."""

    def __init__(self, param: str, expected: str, actual: str, severity: str = "WARNING"):
        self.param = param
        self.expected = expected
        self.actual = actual
        self.severity = severity

    def __str__(self) -> str:
        return (
            f"Modelfile {self.param}: expected {self.expected}, got {self.actual} ({self.severity})"
        )

    def to_dict(self) -> dict:
        return {
            "param": self.param,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
        }


def parse_modelfile(modelfile_text: str) -> dict:
    """Parse an Ollama Modelfile into a dict of PARAMETER → value.

    Example Modelfile::

        FROM ./qwen3.gguf
        PARAMETER temperature 0.7
        PARAMETER presence_penalty 1.5
        PARAMETER num_ctx 32768
        ADAPTER ./mmproj.gguf

    Returns ``{"temperature": "0.7", "presence_penalty": "1.5", "num_ctx": "32768"}``.
    Lines that aren't PARAMETER are ignored (FROM, ADAPTER, TEMPLATE, SYSTEM, etc.).
    """
    params = {}
    for line in modelfile_text.splitlines():
        line = line.strip()
        # Match "PARAMETER <name> <value>"
        m = re.match(r"^PARAMETER\s+(\S+)\s+(.+)$", line, re.IGNORECASE)
        if m:
            param_name = m.group(1).lower()
            param_value = m.group(2).strip()
            params[param_name] = param_value
    return params


def _run_ollama_show(model: str) -> str | None:
    """Run ``ollama show --modelfile <model>`` and return the output.

    Returns ``None`` if the command fails (Ollama not running, model not found, etc.).
    """
    try:
        result = subprocess.run(
            ["ollama", "show", "--modelfile", model],
            capture_output=True,
            text=True,
            timeout=_OLLAMA_SHOW_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def check_modelfile_integrity(model: str) -> tuple[bool, list[ModelfileIssue]]:
    """Check a model's Modelfile for expected parameters.

    For Qwen3 models (detected by "qwen" in the name, case-insensitive):
    - Assert ``presence_penalty=1.5`` (V18.2.41: 0.0 causes thinking-mode leaks)

    For all models:
    - Warn if ``temperature`` is missing (should be set explicitly)
    - Warn if ``num_ctx`` is missing (should be set explicitly)

    Returns ``(is_ok, issues)``:
    - ``(True, [])`` — all checks passed.
    - ``(True, [warnings...])`` — passed but with warnings (fail-open).
    - ``(False, [errors...])`` — critical checks failed (still fail-open in practice;
      the caller logs but proceeds).

    **Fail-open design**: This check is advisory. A failed check logs a WARNING
    but doesn't block the model load — the user may have intentionally set
    non-default parameters.
    """
    issues: list[ModelfileIssue] = []
    model_lower = model.lower()

    # Get the Modelfile
    modelfile_text = _run_ollama_show(model)
    if modelfile_text is None:
        # Can't check — Ollama not running or model not found.
        # This is not an error (the model might be loaded differently).
        return True, []

    params = parse_modelfile(modelfile_text)

    # Qwen3-specific: presence_penalty MUST be 1.5 (V18.2.41 critical fix)
    is_qwen = "qwen" in model_lower or "qwythos" in model_lower
    if is_qwen:
        pp = params.get("presence_penalty", "")
        if pp == "":
            issues.append(
                ModelfileIssue(
                    param="presence_penalty",
                    expected="1.5",
                    actual="(missing)",
                    severity="ERROR",
                )
            )
        elif pp != "1.5":
            issues.append(
                ModelfileIssue(
                    param="presence_penalty",
                    expected="1.5",
                    actual=pp,
                    severity="ERROR",
                )
            )

    # Universal: temperature should be set
    if "temperature" not in params:
        issues.append(
            ModelfileIssue(
                param="temperature",
                expected="(set explicitly)",
                actual="(missing)",
                severity="WARNING",
            )
        )

    # Universal: num_ctx should be set
    if "num_ctx" not in params:
        issues.append(
            ModelfileIssue(
                param="num_ctx",
                expected="(set explicitly)",
                actual="(missing)",
                severity="WARNING",
            )
        )

    # is_ok = no ERROR-severity issues (WARNINGs are acceptable)
    has_errors = any(i.severity == "ERROR" for i in issues)
    return not has_errors, issues
