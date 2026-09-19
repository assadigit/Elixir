"""Settings schema validation + env-var secret resolution (V10.4.0 Phase 6B).

Three layers of defence against silent misconfiguration:

1. **Known-keys validation** — derives the set of valid keys at every nesting
   level from ``Settings._defaults()``.  Catches typos like ``sumarisation``
   instead of ``summarisation`` with a clear, actionable error pointing to
   the closest valid key.  Zero maintenance — auto-syncs with ``_defaults()``
   so new settings are recognised automatically.

2. **Pydantic type validation** (optional) — when pydantic is installed, a
   ``SettingsSchema`` model validates the *types* of critical scalar fields
   (``max_workers`` is int, ``temperature`` is float, ``coverage_threshold``
   is numeric, API keys are strings, etc.).  Falls back to a no-op when
   pydantic is absent so the app runs dependency-free.

3. **Env-var secret resolution** — ``${env:VAR}`` and ``${VAR}`` patterns in
   string settings are resolved from ``os.environ`` at read time, so API
   keys never need to live in ``settings.json`` (which may be synced to
   cloud storage or shared).  Unresolved variables expand to the empty
   string with a logged warning.

Usage from ``utils/settings.py``::

    from utils.settings_schema import validate_settings, resolve_env_vars

    errors = validate_settings(self._data, self._defaults())
    for e in errors:
        logger.warning(e)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

# ── Env-var pattern matching ──────────────────────────────────────────────
# Matches ${env:VAR_NAME} and ${VAR_NAME}.  VAR_NAME must be a valid shell
# identifier (letters, digits, underscore; must not start with a digit).

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{(?:env:)?([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_env_vars(value: Any) -> Any:
    """Resolve ``${env:VAR}`` / ``${VAR}`` patterns in a string setting.

    - If ``value`` is not a string, returns it unchanged.
    - For each ``${env:VAR}`` or ``${VAR}`` occurrence, substitutes the
      value of ``os.environ[VAR]``.  If the variable is unset, substitutes
      the empty string and logs a warning (returned via the second element
      of the tuple in :func:`resolve_env_vars_with_warnings`).
    - Non-pattern strings are returned unchanged.

    This lets users store API keys in environment variables instead of
    ``settings.json``::

        # settings.json
        "summarisation": { "api_key": "${env:OPENROUTER_API_KEY}" }

    The pattern is intentionally simple — no default values, no nesting.
    For anything more complex, use a real secrets manager.
    """
    resolved, _ = resolve_env_vars_with_warnings(value)
    return resolved


def resolve_env_vars_with_warnings(value: Any) -> tuple[Any, list[str]]:
    """Like :func:`resolve_env_vars` but also returns a list of warnings.

    Returns ``(resolved_value, warnings)`` where ``warnings`` is a list of
    human-readable strings for any env vars that were referenced but not
    set in the environment.
    """
    if not isinstance(value, str):
        return value, []
    warnings: list[str] = []

    def _sub(match: re.Match) -> str:
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            warnings.append(
                f"Environment variable '{var_name}' referenced in a setting "
                f"is not set — expanded to empty string."
            )
            return ""
        return env_val

    resolved = _ENV_PATTERN.sub(_sub, value)
    return resolved, warnings


# ── Known-keys validation ─────────────────────────────────────────────────
def _derive_known_keys(defaults: Any, prefix: str = "") -> list[str]:
    """Recursively walk ``defaults`` and return the set of valid dot-paths.

    A dot-path is e.g. ``"summarisation.max_workers"`` or
    ``"translation.outputs.briefing"``.  Leaf values (scalars/lists) are
    returned as paths; nested dicts are recursed into.
    """
    paths: list[str] = []
    if not isinstance(defaults, dict):
        return paths
    for key, val in defaults.items():
        full = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        paths.append(full)
        if isinstance(val, dict):
            paths.extend(_derive_known_keys(val, full))
    return paths


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein edit distance (case-sensitive)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = curr
    return prev[-1]


def _suggest(key: str, valid_keys: list[str]) -> str | None:
    """Return the closest valid key by edit distance, or None if none close."""
    if not valid_keys:
        return None
    # Compare case-insensitively for suggestion quality, but return the
    # original-case valid key.
    lower_valid = [(k.lower(), k) for k in valid_keys]
    kl = key.lower()
    best, best_dist = None, None
    for lk, orig in lower_valid:
        d = _levenshtein(kl, lk)
        if best_dist is None or d < best_dist:
            best, best_dist = orig, d
    # Only suggest if reasonably close (within 40% of key length, min 3).
    threshold = max(3, int(len(key) * 0.4))
    if best_dist is not None and best_dist <= threshold:
        return best
    return None


def validate_settings(data: dict[str, Any], defaults: dict[str, Any]) -> list[str]:
    """Validate ``data`` against the known-keys schema derived from ``defaults``.

    Returns a list of human-readable error strings.  An empty list means the
    settings are valid (no unknown keys).  Each error includes a suggestion
    for the closest valid key when one exists::

        Unknown setting 'sumarisation.api_key'. Did you mean
        'summarisation.api_key'? Valid sections: ocr, postprocess, ...

    This is a *warning-level* validator — it never raises.  The caller
    decides whether to log, abort, or strip the unknown key.
    """
    errors: list[str] = []
    known_paths = set(_derive_known_keys(defaults))
    # Also allow section-level paths (e.g. "summarisation" itself).
    known_sections = set()
    for p in known_paths:
        parts = p.split(".")
        for i in range(1, len(parts) + 1):
            known_sections.add(".".join(parts[:i]))

    def _walk(d: Any, prefix: str) -> None:
        if not isinstance(d, dict):
            return
        for key, val in d.items():
            full = f"{prefix}.{key}" if prefix else key
            if full not in known_sections:
                # Unknown key — find a suggestion among siblings at the same
                # nesting level for better accuracy.
                parent_path = prefix
                sibling_keys = []
                if parent_path:
                    parent = defaults
                    for part in parent_path.split("."):
                        if isinstance(parent, dict) and part in parent:
                            parent = parent[part]
                        else:
                            parent = None
                            break
                    if isinstance(parent, dict):
                        sibling_keys = list(parent.keys())
                else:
                    sibling_keys = list(defaults.keys())
                suggestion = _suggest(key, sibling_keys)
                msg = f"Unknown setting '{full}'."
                if suggestion:
                    msg += (
                        f" Did you mean '{parent_path + '.' if parent_path else ''}{suggestion}'?"
                    )
                msg += (
                    f" Valid keys at this level: {', '.join(sorted(sibling_keys))}."
                    if sibling_keys
                    else ""
                )
                errors.append(msg)
                continue
            if isinstance(val, dict):
                _walk(val, full)

    _walk(data, "")
    return errors


def validate_setting_path(path: str, defaults: dict[str, Any]) -> str | None:
    """Validate a single dot-path against the schema.

    Returns ``None`` if the path is valid, or an error string (with a
    suggestion) if the section or key is unknown.  Used by
    ``Settings.set()`` to fail fast on typos before persisting.
    """
    known_paths = set(_derive_known_keys(defaults))
    known_sections = set()
    for p in known_paths:
        parts = p.split(".")
        for i in range(1, len(parts) + 1):
            known_sections.add(".".join(parts[:i]))
    if path in known_sections:
        return None
    # Find suggestion: walk to the parent, suggest among siblings.
    parts = path.split(".")
    parent_path = ".".join(parts[:-1])
    key = parts[-1]
    parent = defaults
    for part in parent_path.split(".") if parent_path else []:
        if isinstance(parent, dict) and part in parent:
            parent = parent[part]
        else:
            parent = None
            break
    if isinstance(parent, dict):
        sibling_keys = list(parent.keys())
    else:
        sibling_keys = list(defaults.keys())
    suggestion = _suggest(key, sibling_keys)
    msg = f"Unknown setting path '{path}'."
    if suggestion:
        msg += f" Did you mean '{parent_path + '.' if parent_path else ''}{suggestion}'?"
    if sibling_keys:
        msg += f" Valid keys: {', '.join(sorted(sibling_keys))}."
    return msg


# ── Optional Pydantic type validation ─────────────────────────────────────
# Validates the TYPES of critical scalar fields.  When pydantic is not
# installed, :func:`validate_types` is a no-op (returns an empty list) so
# the app runs dependency-free.  Add pydantic to requirements.txt to enable.
try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

    _PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover — pydantic is optional
    _PYDANTIC_AVAILABLE = False


if _PYDANTIC_AVAILABLE:

    class _SummarisationSchema(BaseModel):
        model_config = ConfigDict(extra="allow")
        max_workers: int = Field(ge=1, le=8)
        temperature: float = Field(ge=0.0, le=2.0)
        coverage_threshold: float = Field(ge=0, le=100)
        max_context_tokens: int = Field(ge=512)
        max_output_tokens: int = Field(ge=64)
        api_key: str = ""
        claude_api_key: str = ""
        freellmapi_key: str = ""

        @field_validator("coverage_threshold", mode="before")
        @classmethod
        def _coerce_coverage(cls, v: Any) -> Any:
            # Stored as int (50) historically; accept int or float.
            return float(v)

    class _OcrSchema(BaseModel):
        model_config = ConfigDict(extra="allow")
        timeout: int = Field(ge=30)
        retries: int = Field(ge=0, le=10)
        image_max_size: int = Field(ge=256, le=8192)
        image_dpi: int = Field(ge=72, le=1200)

    class _TranslationSchema(BaseModel):
        model_config = ConfigDict(extra="allow")
        temperature: float = Field(ge=0.0, le=2.0)
        max_chunk_tokens: int = Field(ge=64)
        back_translation_threshold: float = Field(ge=0.0, le=1.0)
        judge_threshold: float = Field(ge=0.0, le=1.0)
        max_retries: int = Field(ge=0, le=5)

    class _EmbeddingSchema(BaseModel):
        """V18.4 (Phase 2): type validation for the embedding section.

        Validates the two new optional-mode knobs:
          - ``enabled``    — bool, gates the semantic-similarity path.
          - ``fallback``  — str, one of {"jaccard", "skip"}; decides what
            happens when ``enabled=False``. "jaccard" (default) keeps a real
            (weaker) lexical signal; "skip" omits Phase 2.2 entirely.

        Other embedding keys (model, device, cache_enabled, load_mode,
        threshold_scale) are allowed through ``extra="allow"`` so the schema
        never blocks forward-compat additions.
        """

        model_config = ConfigDict(extra="allow")
        enabled: bool = True
        fallback: str = "jaccard"

        @field_validator("fallback")
        @classmethod
        def _validate_fallback(cls, v: Any) -> Any:
            if v not in ("jaccard", "skip"):
                raise ValueError(f"embedding.fallback must be 'jaccard' or 'skip' (got {v!r})")
            return v

    class _UiSchema(BaseModel):
        model_config = ConfigDict(extra="allow")
        shutdown_countdown_sec: int = Field(ge=10, le=600)

    class SettingsSchema(BaseModel):
        """Top-level settings type validator.

        Only the critical scalar fields are typed; unknown sections/keys are
        allowed (``extra="allow"`` on sub-models) so the schema never blocks
        forward-compat additions.  Typo detection is handled by the
        known-keys validator above; this model catches *type* errors (e.g.
        ``max_workers: "two"`` instead of ``2``).
        """

        model_config = ConfigDict(extra="allow")
        summarisation: _SummarisationSchema | None = None
        ocr: _OcrSchema | None = None
        translation: _TranslationSchema | None = None
        embedding: _EmbeddingSchema | None = None
        ui: _UiSchema | None = None

    def validate_types(data: dict[str, Any]) -> list[str]:
        """Validate critical scalar types via the Pydantic schema.

        Returns a list of human-readable error strings (empty = valid).
        """
        try:
            SettingsSchema.model_validate(data)
            return []
        except ValidationError as exc:
            errs: list[str] = []
            for err in exc.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "invalid")
                errs.append(f"Type error in '{loc}': {msg}")
            return errs

else:  # pydantic not installed — no-op

    def validate_types(data: dict[str, Any]) -> list[str]:
        return []
