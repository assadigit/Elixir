"""V0.6.23 (W-i1): a JSON schema + validator for podcast script files.

Why this exists
---------------
The wizard's "Export Script" button writes a JSON file via
``ScriptResult.to_json()``. The CLI's `_load_script_json` reads it
back via ``ScriptResult.from_json()``. But there's a real asymmetry:

  - ``to_json`` serializes only 4 fields (lines, coverage_pct,
    bullets_covered, bullets_missing). It DROPS title, bullets_input,
    retries, forced_segments, error.
  - ``from_json`` is lenient — defaults missing fields, accepts raw
    arrays (just the lines), accepts JSONL, strips [Host A] prefixes.
    Useful for hand-edited files, but it means a malformed file (e.g.,
    a line with host="C" or segment_type=42) is silently accepted
    with garbage defaults instead of rejected.

Before V0.6.23, there was no way for the operator to verify a script
JSON file matches the expected schema BEFORE feeding it to `generate`.
A typo in the JSON (e.g., `"host": "Alice"` instead of `"host": "A"`)
would propagate through validation (the V0.6.19 validator would catch
the bad host) but the operator would have to run validate first. A
schema check at the JSON-structure level catches it earlier + with
clearer messages ("lines[2].host: expected 'A' or 'B', got 'Alice'").

This module provides:

  1. ``SCRIPT_SCHEMA`` — a dict describing the expected JSON schema
     (the format `ScriptResult.to_json` SHOULD produce + the extra
     fields `from_json` reads). Pure-Python dict — no jsonschema
     dependency (that's not in every rig's venv).
  2. ``validate_script_json(data)`` — validate a parsed JSON dict
     against the schema. Returns a list of ``SchemaIssue`` objects
     (path, message, severity). Pure-Python, no jsonschema.
  3. ``validate_script_file(path)`` — load a JSON file + validate it.
     Returns the same ``SchemaValidationResult``.
  4. ``format_schema_for_display()`` — pretty-print the schema as a
     human-readable doc (for the CLI's `schema` subcommand).
  5. ``format_issues_for_display(result)`` — format the validation
     issues as a multi-line string (git-diff-style: the JSON path +
     the error).

The validator checks:
  - Top-level: must be a dict with "lines" (required).
  - ``lines``: must be a non-empty list of dicts.
  - Each line: ``host`` must be "A" or "B"; ``text`` must be a non-
    empty string; ``segment_type`` must be one of the known types
    (intro/content/conclusion); ``source_ref`` must be a string
    (may be empty).
  - ``title``: if present, must be a string.
  - ``coverage_pct``: if present, must be a number 0-100.
  - ``bullets_covered`` / ``bullets_missing``: if present, must be
    lists of ints.
  - ``bullets_input``: if present, must be a list of strings.
  - ``retries`` / ``forced_segments``: if present, must be non-negative
    ints.
  - ``error``: if present, must be a string or null.

The validator does NOT reject unknown fields (forward-compat: a newer
app version may add fields an older validator doesn't know).

Public API:
  - ``SCRIPT_SCHEMA`` — the schema dict.
  - ``SchemaIssue`` / ``SchemaValidationResult`` dataclasses.
  - ``validate_script_json(data)`` — validate a parsed dict.
  - ``validate_script_file(path)`` — load + validate a JSON file.
  - ``format_schema_for_display()`` — human-readable schema doc.
  - ``format_issues_for_display(result)`` — multi-line issue formatter.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# ── The schema (a plain dict, no jsonschema dependency) ─────────────────────

# The known segment_type values the script_generator produces. A line
# with a different segment_type is a WARNING (not an error — the audio
# generator doesn't care about segment_type, but the validator's W3/W4
# checks expect intro/conclusion).
_KNOWN_SEGMENT_TYPES = ("intro", "content", "conclusion")

# The schema dict — a human + machine readable description of the
# expected JSON format. Used by format_schema_for_display() to produce
# the CLI's `schema` doc, AND by validate_script_json() as the source
# of truth for the validation rules.
SCRIPT_SCHEMA: dict = {
    "type": "object",
    "description": "A podcast script JSON file (the format ScriptResult.to_json produces).",
    "required": ["lines"],
    "fields": {
        "lines": {
            "type": "array",
            "required": True,
            "description": "The script's dialogue lines, in order.",
            "min_items": 1,
            "items": {
                "type": "object",
                "required": ["host", "text"],
                "fields": {
                    "host": {
                        "type": "string",
                        "enum": ["A", "B"],
                        "description": "Which host speaks this line.",
                    },
                    "text": {
                        "type": "string",
                        "min_length": 1,
                        "description": "The dialogue text (may contain [vocal cues]).",
                    },
                    "source_ref": {
                        "type": "string",
                        "required": False,
                        "description": "Audit-trail reference to the source bullet/segment.",
                    },
                    "segment_type": {
                        "type": "string",
                        "enum": list(_KNOWN_SEGMENT_TYPES),
                        "required": False,
                        "description": "intro / content / conclusion (the validator expects intro first, conclusion last).",
                    },
                },
            },
        },
        "title": {
            "type": "string",
            "required": False,
            "description": "The podcast title (used for the output filename).",
        },
        "coverage_pct": {
            "type": "number",
            "min": 0,
            "max": 100,
            "required": False,
            "description": "Anti-hallucination coverage percentage (0-100).",
        },
        "bullets_input": {
            "type": "array",
            "items": {"type": "string"},
            "required": False,
            "description": "The source bullets the script was generated from.",
        },
        "bullets_covered": {
            "type": "array",
            "items": {"type": "int"},
            "required": False,
            "description": "Indices (into bullets_input) of bullets the LLM covered.",
        },
        "bullets_missing": {
            "type": "array",
            "items": {"type": "int"},
            "required": False,
            "description": "Indices of bullets the LLM skipped (force-inserted by the anti-hallucination system).",
        },
        "retries": {
            "type": "int",
            "min": 0,
            "required": False,
            "description": "How many gap-fill retries the script_generator used.",
        },
        "forced_segments": {
            "type": "int",
            "min": 0,
            "required": False,
            "description": "How many segments were force-inserted.",
        },
        "error": {
            "type": ["string", "null"],
            "required": False,
            "description": "A generation error message (null if no error).",
        },
    },
}


# ── The validation result types ─────────────────────────────────────────────


# Severity constants (string literals — no enum, keeps JSON serialization trivial).
SEVERITY_ERROR = "error"  # blocks generation
SEVERITY_WARNING = "warning"  # allows generation, but worth flagging


@dataclass
class SchemaIssue:
    """One issue found by the schema validator.

    ``path`` is a dotted JSON path (e.g., "lines[2].host"). ``message``
    is the human-readable explanation. ``severity`` is ERROR or WARNING.
    """

    path: str
    message: str
    severity: str = SEVERITY_ERROR

    def __post_init__(self) -> None:
        if self.severity not in (SEVERITY_ERROR, SEVERITY_WARNING):
            raise ValueError(
                f"SchemaIssue.severity must be {SEVERITY_ERROR!r} or "
                f"{SEVERITY_WARNING!r}, got {self.severity!r}"
            )


@dataclass
class SchemaValidationResult:
    """The result of validating a script JSON against the schema."""

    issues: list[SchemaIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[SchemaIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[SchemaIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]

    @property
    def ok(self) -> bool:
        """True iff no ERROR-level issues (warnings are allowed)."""
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok


# ── The validator ───────────────────────────────────────────────────────────


def _check_type(value, expected_type: str, path: str, issues: list[SchemaIssue]) -> bool:
    """Check that ``value`` matches the expected type. Returns True if OK.
    Appends a SchemaIssue on mismatch."""
    if expected_type == "object":
        if not isinstance(value, dict):
            issues.append(SchemaIssue(path, f"expected an object, got {type(value).__name__}"))
            return False
    elif expected_type == "array":
        if not isinstance(value, list):
            issues.append(SchemaIssue(path, f"expected an array, got {type(value).__name__}"))
            return False
    elif expected_type == "string":
        if not isinstance(value, str):
            issues.append(SchemaIssue(path, f"expected a string, got {type(value).__name__}"))
            return False
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            issues.append(SchemaIssue(path, f"expected a number, got {type(value).__name__}"))
            return False
    elif expected_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            issues.append(SchemaIssue(path, f"expected an int, got {type(value).__name__}"))
            return False
    elif expected_type == "string-or-null":
        if value is not None and not isinstance(value, str):
            issues.append(
                SchemaIssue(path, f"expected a string or null, got {type(value).__name__}")
            )
            return False
    return True


def validate_script_json(data) -> SchemaValidationResult:
    """Validate a parsed JSON dict against the script schema.

    Args:
        data: the parsed JSON (must be a dict; a list is accepted as a
            raw-lines shorthand with a WARNING).

    Returns:
        A SchemaValidationResult with .issues / .errors / .warnings / .ok.
    """
    issues: list[SchemaIssue] = []

    # Top-level must be a dict (or a list — the raw-lines shorthand).
    if isinstance(data, list):
        # Raw-lines shorthand — accept with a warning (from_json accepts it).
        issues.append(
            SchemaIssue(
                path="$",
                message=(
                    "Top-level JSON is an array (raw-lines shorthand). "
                    "Accepted, but a top-level object with a 'lines' field "
                    "is the canonical format."
                ),
                severity=SEVERITY_WARNING,
            )
        )
        lines = data
    elif isinstance(data, dict):
        if "lines" not in data:
            issues.append(
                SchemaIssue("$", "missing required field: 'lines'", severity=SEVERITY_ERROR)
            )
            return SchemaValidationResult(issues=issues)
        lines = data.get("lines")
    else:
        issues.append(SchemaIssue("$", f"expected an object or array, got {type(data).__name__}"))
        return SchemaValidationResult(issues=issues)

    # lines must be a non-empty array.
    if not _check_type(lines, "array", "$.lines", issues):
        return SchemaValidationResult(issues=issues)
    if len(lines) == 0:
        issues.append(SchemaIssue("$.lines", "must be a non-empty array (the script has no lines)"))
        return SchemaValidationResult(issues=issues)

    # Validate each line.
    for i, line in enumerate(lines):
        line_path = f"$.lines[{i}]"
        if not _check_type(line, "object", line_path, issues):
            continue
        # host (required, must be "A" or "B").
        if "host" not in line:
            issues.append(SchemaIssue(line_path, "missing required field: 'host'"))
        else:
            host = line["host"]
            if not _check_type(host, "string", f"{line_path}.host", issues):
                pass
            elif host not in ("A", "B"):
                issues.append(
                    SchemaIssue(
                        f"{line_path}.host",
                        f"expected 'A' or 'B', got {host!r}",
                    )
                )
        # text (required, non-empty string).
        if "text" not in line:
            issues.append(SchemaIssue(line_path, "missing required field: 'text'"))
        else:
            text = line["text"]
            if not _check_type(text, "string", f"{line_path}.text", issues):
                pass
            elif not text.strip():
                issues.append(SchemaIssue(f"{line_path}.text", "must be a non-empty string"))
        # source_ref (optional, must be a string if present).
        if "source_ref" in line:
            _check_type(line["source_ref"], "string", f"{line_path}.source_ref", issues)
        # segment_type (optional, must be a known type if present).
        if "segment_type" in line:
            seg = line["segment_type"]
            if not _check_type(seg, "string", f"{line_path}.segment_type", issues):
                pass
            elif seg not in _KNOWN_SEGMENT_TYPES:
                issues.append(
                    SchemaIssue(
                        f"{line_path}.segment_type",
                        f"expected one of {_KNOWN_SEGMENT_TYPES}, got {seg!r}",
                        severity=SEVERITY_WARNING,  # not fatal — audio gen ignores it
                    )
                )

    # If top-level is a dict, validate the metadata fields.
    if isinstance(data, dict):
        # title (optional string).
        if "title" in data:
            _check_type(data["title"], "string", "$.title", issues)
        # coverage_pct (optional number 0-100).
        if "coverage_pct" in data:
            cp = data["coverage_pct"]
            if _check_type(cp, "number", "$.coverage_pct", issues):
                if cp < 0 or cp > 100:
                    issues.append(SchemaIssue("$.coverage_pct", f"expected 0-100, got {cp}"))
        # bullets_input (optional list of strings).
        if "bullets_input" in data:
            if _check_type(data["bullets_input"], "array", "$.bullets_input", issues):
                for j, b in enumerate(data["bullets_input"]):
                    _check_type(b, "string", f"$.bullets_input[{j}]", issues)
        # bullets_covered (optional list of ints).
        if "bullets_covered" in data:
            if _check_type(data["bullets_covered"], "array", "$.bullets_covered", issues):
                for j, b in enumerate(data["bullets_covered"]):
                    _check_type(b, "int", f"$.bullets_covered[{j}]", issues)
        # bullets_missing (optional list of ints).
        if "bullets_missing" in data:
            if _check_type(data["bullets_missing"], "array", "$.bullets_missing", issues):
                for j, b in enumerate(data["bullets_missing"]):
                    _check_type(b, "int", f"$.bullets_missing[{j}]", issues)
        # retries (optional non-negative int).
        if "retries" in data:
            r = data["retries"]
            if _check_type(r, "int", "$.retries", issues) and r < 0:
                issues.append(SchemaIssue("$.retries", f"expected >= 0, got {r}"))
        # forced_segments (optional non-negative int).
        if "forced_segments" in data:
            fs = data["forced_segments"]
            if _check_type(fs, "int", "$.forced_segments", issues) and fs < 0:
                issues.append(SchemaIssue("$.forced_segments", f"expected >= 0, got {fs}"))
        # error (optional string or null).
        if "error" in data:
            _check_type(data["error"], "string-or-null", "$.error", issues)

    return SchemaValidationResult(issues=issues)


def validate_script_file(path: Path) -> SchemaValidationResult:
    """Load a JSON file + validate it against the schema.

    Args:
        path: the path to the JSON file.

    Returns:
        A SchemaValidationResult. If the file can't be read or parsed,
        the result has a single ERROR-level issue with the read/parse
        error message (the function never raises).
    """
    issues: list[SchemaIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        issues.append(SchemaIssue("$", f"failed to read file: {e}"))
        return SchemaValidationResult(issues=issues)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        issues.append(SchemaIssue("$", f"invalid JSON: {e}"))
        return SchemaValidationResult(issues=issues)
    return validate_script_json(data)


# ── The formatters ───────────────────────────────────────────────────────────


def format_schema_for_display(
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format the SCRIPT_SCHEMA as a human-readable doc for the CLI's
    `schema` subcommand. Each field is shown with its type, required-ness,
    and description."""
    parts: list[str] = []
    parts.append("📋 Podcast Script JSON Schema")
    parts.append("═" * 60)
    parts.append(f"Description: {SCRIPT_SCHEMA['description']}")
    parts.append(f"Required top-level fields: {', '.join(SCRIPT_SCHEMA['required'])}")
    parts.append("─" * 60)
    parts.append("Fields:")
    parts.append("")
    for name, field_spec in SCRIPT_SCHEMA["fields"].items():
        req = field_spec.get("required", False)
        req_str = "REQUIRED" if req else "optional"
        ftype = field_spec["type"]
        if isinstance(ftype, list):
            ftype_str = " | ".join(ftype)
        else:
            ftype_str = ftype
        parts.append(f"  {name} ({ftype_str}, {req_str})")
        parts.append(f"    {field_spec['description']}")
        if "enum" in field_spec:
            parts.append(f"    Allowed values: {field_spec['enum']}")
        if "min" in field_spec or "max" in field_spec:
            mn = field_spec.get("min", "-∞")
            mx = field_spec.get("max", "+∞")
            parts.append(f"    Range: {mn} to {mx}")
        if "min_items" in field_spec:
            parts.append(f"    Min items: {field_spec['min_items']}")
        if "items" in field_spec:
            item_type = field_spec["items"]["type"]
            parts.append(f"    Item type: {item_type}")
        parts.append("")
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out


def format_issues_for_display(
    result: SchemaValidationResult,
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format a SchemaValidationResult as a multi-line string.

    If the result is clean (no issues), returns "✅ No schema issues —
    the file matches the expected format.". Otherwise, groups by
    severity (ERROR first, then WARNING) with the JSON path + message.
    """
    if not result.issues:
        msg = "✅ No schema issues — the file matches the expected format."
        if log:
            log(msg, "INFO")
        return msg

    parts: list[str] = []
    for severity, label in (
        (SEVERITY_ERROR, "ERROR"),
        (SEVERITY_WARNING, "WARNING"),
    ):
        subset = [i for i in result.issues if i.severity == severity]
        if not subset:
            continue
        parts.append(f"{label} ({len(subset)}):")
        for issue in subset:
            parts.append(f"  [{issue.path}] {issue.message}")
            if log:
                log(f"  [{issue.path}] {issue.message}", severity.upper())

    return "\n".join(parts)
