"""V18.2.21 (Phase 1.2) — Structured-output adapter for LLM responses.

The problem
-----------
``response_parser.py`` parses the model's XML-tagged output with ~30
``re.search`` / ``re.findall`` patterns and ≥7 fallback strategies. Every
model that emits slightly different markup (extra whitespace, nested tags,
Markdown fences, a stray ``<system>`` leak) hits a different fallback path,
and content is *silently dropped* when no pattern matches. There is no
schema enforcement — a malformed ``<bullet_points>`` block becomes ``[]``
with no error.

The fix (2026 standard)
-----------------------
Provider structured-output / JSON mode. Ollama supports ``format: "json"``
(since 0.1.34); OpenAI supports ``response_format: {"type": "json_object"}``;
Anthropic supports tool-use for structured output. When the provider returns
JSON, we validate it against a Pydantic ``SummarySchema`` — a *single*
validated contract instead of 30 regexes.

Design: JSON-first, XML-fallback (graceful degradation)
-------------------------------------------------------
This module is **opt-in and non-breaking**. The existing XML path stays as
the fallback for:
- Models without JSON mode (e.g. low-bit IQ2_XXS quants — Key Decision #5:
  Academic Rigor disabled for low-bit quants because they can't follow the
  complex JSON prompt).
- Providers without structured-output support.
- Any JSON parse/validation failure (falls back to the XML parser).

The caller requests structured output with ``structured=SummarySchema``;
if the provider/model can't deliver, the adapter returns the raw string
and the caller's existing XML parse path handles it.

Book-agnostic (Key Decision #3): the schema describes STRUCTURE only
(section names + types), never content. No book-specific fields.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Pydantic is an optional dependency (the app runs dependency-free). When
# unavailable, structured validation degrades to a dict-shape check and the
# caller falls back to the XML parser. This matches the existing
# settings_schema.py pattern.
try:
    from pydantic import BaseModel, Field, ValidationError

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover — pydantic is in requirements
    _HAS_PYDANTIC = False
    BaseModel = object  # type: ignore[assignment, misc]
    ValidationError = ValueError  # type: ignore[assignment, misc]

    class Field:  # type: ignore[no-redef]
        """Minimal Field shim when pydantic is absent (for class body only)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.default = kwargs.get("default")
            self.description = kwargs.get("description", "")


# ── The summary schema (the single validated contract) ─────────────────────


class SummarySchema(BaseModel):  # type: ignore[misc, valid-type]
    """The structured-output contract for chapter summaries.

    Mirrors the five XML sections in ``prompts/default.md``:
    ``executive_summary``, ``bullet_points``, ``thorough_summary``,
    ``key_distinctions``, ``theoretical_tensions``.

    All fields are strings or lists of strings — no book-specific types.
    ``key_distinctions`` and ``theoretical_tensions`` are optional (the
    prompt allows "None" when the chapter doesn't discuss them).

    When pydantic is available, ``SummarySchema.model_validate_json(raw)``
    enforces types and raises ``ValidationError`` on violation. When
    pydantic is absent, ``validate_summary_dict`` does a manual shape check.
    """

    executive_summary: str = Field(
        ..., description="Source-scaled overview of the chapter's main concepts."
    )
    bullet_points: list[str] = Field(
        ...,
        description="Source-scaled distinct key takeaways, one per item.",
    )
    thorough_summary: str = Field(
        ...,
        description="Source-scaled detailed analysis as flowing prose.",
    )
    key_distinctions: str | None = Field(
        None,
        description="2-5 distinctions the chapter explicitly draws, or None.",
    )
    theoretical_tensions: str | None = Field(
        None,
        description="2-4 theoretical tensions/debates, or None.",
    )


# ── Provider capability detection ──────────────────────────────────────────


def supports_json_mode(provider: str, model: str) -> bool:
    """Heuristic: does this provider+model combination support JSON mode?

    Args:
        provider: "ollama" | "openai_compat" | "claude" | "freellmapi".
        model: the model tag.

    Returns:
        True if the provider supports structured JSON output for this model.

    Notes:
        - Ollama: supports ``format: "json"`` for all models (0.1.34+), BUT
          low-bit quants (IQ2_XXS/XS) cannot follow complex JSON prompts
          reliably (Key Decision #5). We return False for those so the
          caller uses the simpler XML path.
        - OpenAI-compat: supports ``response_format: {"type": "json_object"}``
          for most models.
        - Claude: supports tool-use for structured output (always True).
        - Unknown providers: False (safe default — fall back to XML).
    """
    if not provider or not model:
        return False
    provider_l = provider.lower()
    model_l = model.lower()

    # Key Decision #5: Academic Rigor disabled for low-bit quants — they
    # can't follow the complex JSON prompt. The same applies to JSON mode.
    if "iq2_xxs" in model_l or "iq2_xs" in model_l or "iq1" in model_l:
        return False

    if provider_l == "ollama":
        return True
    if provider_l in ("openai_compat", "freellmapi"):
        return True
    if provider_l == "claude":
        return True
    # V0.04: llama.cpp server supports the OpenAI ``response_format:
    # {"type": "json_object"}`` request (llama-server, 2024+ builds); the
    # provider maps json_mode onto it exactly like openai_compat.
    if provider_l == "llamacpp":
        return True
    return False


def build_json_instruction(schema_cls: type, source_words: int | None = None) -> str:
    """Build a JSON-formatting instruction to append to the prompt.

    Tells the model to output a JSON object matching the schema. Kept short
    so it doesn't bloat the context window for low-VRAM models.

    V0.05 (rig audit F9b): the length hints scale to the source via
    ``length_policy`` when ``source_words`` is provided (the old fixed
    "150-250 word" / "20-40" / "800-1200 word" hints carried the
    expansion-by-instruction defect); without it they degrade to a
    source-relative phrasing with no absolute numbers.
    """
    if schema_cls is SummarySchema:
        try:
            from core.summarisation.length_policy import (
                bullet_range_phrase,
                exec_words_phrase,
                thorough_words_phrase,
            )

            if source_words:
                _exec_hint = exec_words_phrase(int(source_words))
                _bullet_hint = f"{bullet_range_phrase(int(source_words))} distinct key takeaways"
                _thorough_hint = f"{thorough_words_phrase(int(source_words))} detailed analysis"
            else:
                raise ValueError  # fall through to the source-relative wording
        except Exception:
            _exec_hint = "source-scaled overview"
            _bullet_hint = "source-scaled distinct key takeaways"
            _thorough_hint = "source-scaled detailed analysis"
        return (
            "\n\n### OUTPUT FORMAT (JSON) ###\n"
            "Output ONLY a JSON object with these keys (no markdown, no "
            "code fences, no commentary):\n"
            "{\n"
            f'  "executive_summary": "{_exec_hint}",\n'
            f'  "bullet_points": ["{_bullet_hint}", ...],\n'
            f'  "thorough_summary": "{_thorough_hint}",\n'
            '  "key_distinctions": "2-5 distinctions, or null",\n'
            '  "theoretical_tensions": "2-4 tensions, or null"\n'
            "}\n"
            "If the chapter does not discuss distinctions or tensions, use "
            'null (not the string "None").'
        )
    # Generic fallback for other schemas
    return (
        "\n\n### OUTPUT FORMAT (JSON) ###\n"
        "Output ONLY a valid JSON object matching the requested schema. "
        "No markdown, no code fences, no commentary.\n"
    )


# ── Validation ─────────────────────────────────────────────────────────────


def validate_summary_json(raw: str) -> dict[str, Any] | None:
    """Parse + validate a JSON LLM response against ``SummarySchema``.

    Args:
        raw: the raw LLM response text (may contain leading/trailing
            whitespace, markdown fences, or a preamble — all stripped).

    Returns:
        A validated dict with keys ``executive_summary``, ``bullet_points``,
        ``thorough_summary``, ``key_distinctions``, ``theoretical_tensions``
        on success; ``None`` on failure (caller falls back to XML parser).

    The function NEVER raises — it returns None on any parse/validation
    failure so the caller can gracefully fall back to the XML path.
    """
    if not raw or not raw.strip():
        return None

    cleaned = _extract_json(raw)
    if cleaned is None:
        logger.debug("structured_io: no JSON object found in response — falling back to XML")
        return None

    if _HAS_PYDANTIC:
        try:
            schema = SummarySchema.model_validate_json(cleaned)
            return schema.model_dump()
        except ValidationError as exc:
            logger.debug(
                "structured_io: JSON failed Pydantic validation (%s) — falling back to XML",
                exc,
            )
            return None
        except Exception as exc:
            logger.debug(
                "structured_io: JSON parse error (%s: %s) — falling back to XML",
                type(exc).__name__,
                exc,
            )
            return None

    # No pydantic — manual shape check
    return _manual_validate(cleaned)


def _extract_json(raw: str) -> str | None:
    """Extract the first JSON object from a raw LLM response.

    Handles:
    - Bare JSON object (the ideal case).
    - JSON wrapped in ```json ... ``` markdown fences.
    - JSON with a preamble before it (model ignored instructions).
    - JSON with trailing text after it.
    """
    text = raw.strip()
    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    # Find the first {...} block (greedy enough to catch nested braces)
    start = text.find("{")
    if start == -1:
        return None
    # Walk the string counting braces to find the matching close
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None  # unbalanced braces


def _manual_validate(json_str: str) -> dict[str, Any] | None:
    """Manual shape check when pydantic is unavailable.

    Validates: JSON parses, has the 3 required keys with correct types.
    Optional keys (key_distinctions, theoretical_tensions) may be absent
    or null.
    """
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    required = {
        "executive_summary": str,
        "bullet_points": list,
        "thorough_summary": str,
    }
    result: dict[str, Any] = {}
    for key, expected_type in required.items():
        val = data.get(key)
        if not isinstance(val, expected_type):
            logger.debug(
                "structured_io: manual validation failed — key %r expected %s, got %s",
                key,
                expected_type.__name__,
                type(val).__name__ if val is not None else "None",
            )
            return None
        if expected_type is list:
            # bullet_points must be a list of strings
            if not all(isinstance(b, str) for b in val):
                return None
        result[key] = val
    # Optional keys
    for opt_key in ("key_distinctions", "theoretical_tensions"):
        val = data.get(opt_key)
        if val is not None and not isinstance(val, str):
            val = None  # coerce non-string to None
        result[opt_key] = val
    return result


# ── Adapter: call provider with JSON mode, validate, fallback ──────────────


def complete_structured(
    provider: Any,
    prompt: str,
    schema_cls: type = SummarySchema,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    fallback_parser: Any | None = None,
) -> dict[str, Any] | None:
    """Call a provider requesting JSON, validate against ``schema_cls``.

    This is the high-level adapter the summarizer will call. It:
    1. Appends the JSON-format instruction to the prompt.
    2. Calls ``provider.complete`` (the provider injects ``format: "json"``
       or ``response_format`` internally).
    3. Validates the response against the schema.
    4. On ANY failure (no JSON, validation error, provider error), falls
       back to ``fallback_parser(raw)`` if provided, else returns None.

    Args:
        provider: an LLMProvider instance (OllamaProvider, etc.). Must
            have a ``.complete(prompt, ...) -> Optional[str]`` method.
        prompt: the base prompt (without JSON instructions).
        schema_cls: the Pydantic model class to validate against.
        temperature, max_tokens, model: forwarded to provider.complete.
        fallback_parser: optional ``Callable[[str], Dict]`` — invoked with
            the raw response when JSON validation fails. Typically the
            existing ``response_parser.parse_response``.

    Returns:
        Validated dict on success, or the fallback_parser's result, or None.
    """
    if provider is None:
        return None

    json_prompt = prompt + build_json_instruction(schema_cls)
    try:
        raw = provider.complete(
            json_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )
    except Exception as exc:
        logger.debug(
            "structured_io: provider.complete raised %s: %s — falling back",
            type(exc).__name__,
            exc,
        )
        raw = None

    if raw:
        validated = validate_summary_json(raw)
        if validated is not None:
            return validated
        # JSON parse/validation failed — fall back to XML parser on the
        # raw response (the model may have emitted XML despite the JSON
        # instruction; common with low-bit quants).
        if fallback_parser is not None:
            try:
                return fallback_parser(raw)
            except Exception as exc:
                logger.debug(
                    "structured_io: fallback_parser raised %s: %s",
                    type(exc).__name__,
                    exc,
                )
    # Provider returned None or both paths failed — last resort: None
    # signals the caller to handle the empty-response path.
    return None
