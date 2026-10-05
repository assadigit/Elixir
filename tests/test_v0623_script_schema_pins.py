"""V0.6.23 — the JSON-schema + schema-CLI batch pins.

This file pins the V0.6.23 additions:

Layer 1 — the SCRIPT SCHEMA module (W-i1, NEW core/podcast/script_schema.py):
  - ``SCRIPT_SCHEMA`` — a plain-dict description of the expected JSON
    format (no jsonschema dependency).
  - ``validate_script_json(data)`` — validate a parsed JSON dict/list.
  - ``validate_script_file(path)`` — load + validate a JSON file.
  - ``SchemaIssue`` / ``SchemaValidationResult`` dataclasses with
    .errors / .warnings / .ok.
  - ``format_schema_for_display()`` — human-readable schema doc.
  - ``format_issues_for_display(result)`` — multi-line issue formatter.

Layer 2 — the CLI schema subcommand (W-i2, core/podcast/cli.py):
  - ``schema`` subcommand: prints the schema doc, or validates a file
    with ``--validate <FILE>``.
  - Exits 0 on success, 1 on schema ERROR, 2 on file/parse error.

All tests are pure-Python (no PySide6 / no torch / no jsonschema).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared helpers ──────────────────────────────────────────────────────────


def _valid_script_dict() -> dict:
    """A minimal valid script dict (the canonical format)."""
    return {
        "lines": [
            {"host": "A", "text": "intro line", "source_ref": "r1", "segment_type": "intro"},
            {"host": "B", "text": "body line", "source_ref": "r2", "segment_type": "content"},
            {
                "host": "A",
                "text": "conclusion line",
                "source_ref": "r3",
                "segment_type": "conclusion",
            },
        ],
        "title": "test",
        "coverage_pct": 100.0,
        "bullets_input": ["b1", "b2"],
        "bullets_covered": [0, 1],
        "bullets_missing": [],
        "retries": 0,
        "forced_segments": 0,
        "error": None,
    }


def _write_json(path: Path, data) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── Layer 1: the script schema module ───────────────────────────────────────


def test_v0623_validate_valid_script_passes() -> None:
    """A canonical valid script dict produces zero issues."""
    from core.podcast.script_schema import validate_script_json

    result = validate_script_json(_valid_script_dict())
    assert result.ok, f"valid script should pass; got issues: {result.issues}"
    assert result.errors == []
    assert result.warnings == []


def test_v0623_validate_missing_lines_field_blocks() -> None:
    """A dict without 'lines' is an ERROR (the field is required)."""
    from core.podcast.script_schema import validate_script_json

    result = validate_script_json({"title": "no lines"})
    assert not result.ok
    assert len(result.errors) == 1
    assert "lines" in result.errors[0].message


def test_v0623_validate_empty_lines_array_blocks() -> None:
    """An empty 'lines' array is an ERROR (the script has no lines)."""
    from core.podcast.script_schema import validate_script_json

    result = validate_script_json({"lines": []})
    assert not result.ok
    assert len(result.errors) == 1
    assert "non-empty" in result.errors[0].message


def test_v0623_validate_raw_array_shorthand_warns() -> None:
    """A top-level JSON array (raw-lines shorthand) is accepted with a
    WARNING (from_json accepts it; the canonical format is an object)."""
    from core.podcast.script_schema import validate_script_json

    data = [
        {"host": "A", "text": "line 1", "source_ref": "r", "segment_type": "intro"},
        {"host": "A", "text": "line 2", "source_ref": "r", "segment_type": "content"},
    ]
    result = validate_script_json(data)
    assert result.ok, "raw-array shorthand should NOT block (warning only)"
    assert len(result.warnings) == 1
    assert "array" in result.warnings[0].message.lower()


def test_v0623_validate_invalid_host_value_blocks() -> None:
    """A line with host='C' (or any non-A/B value) is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"host": "A", "text": "ok", "source_ref": "r", "segment_type": "intro"},
            {"host": "C", "text": "bad host", "source_ref": "r", "segment_type": "content"},
        ]
    }
    result = validate_script_json(data)
    assert not result.ok
    host_errors = [e for e in result.errors if "host" in e.path]
    assert len(host_errors) == 1
    assert "lines[1].host" in host_errors[0].path


def test_v0623_validate_empty_text_blocks() -> None:
    """A line with empty text is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"host": "A", "text": "", "source_ref": "r", "segment_type": "intro"},
        ]
    }
    result = validate_script_json(data)
    assert not result.ok
    text_errors = [e for e in result.errors if "text" in e.path]
    assert len(text_errors) == 1
    assert "non-empty" in text_errors[0].message


def test_v0623_validate_whitespace_only_text_blocks() -> None:
    """A line with whitespace-only text is an ERROR (the strip() check)."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"host": "A", "text": "   ", "source_ref": "r", "segment_type": "intro"},
        ]
    }
    result = validate_script_json(data)
    assert not result.ok
    assert any("non-empty" in e.message for e in result.errors)


def test_v0623_validate_missing_host_in_line_blocks() -> None:
    """A line without a 'host' field is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"text": "no host", "source_ref": "r", "segment_type": "intro"},
        ]
    }
    result = validate_script_json(data)
    assert not result.ok
    assert any("host" in e.message for e in result.errors)


def test_v0623_validate_missing_text_in_line_blocks() -> None:
    """A line without a 'text' field is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"host": "A", "source_ref": "r", "segment_type": "intro"},
        ]
    }
    result = validate_script_json(data)
    assert not result.ok
    assert any("text" in e.message for e in result.errors)


def test_v0623_validate_unknown_segment_type_warns() -> None:
    """A line with an unknown segment_type (not intro/content/conclusion)
    is a WARNING (not an error — the audio generator ignores segment_type)."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [
            {"host": "A", "text": "ok", "source_ref": "r", "segment_type": "weird"},
        ]
    }
    result = validate_script_json(data)
    assert result.ok, "unknown segment_type should NOT block (warning only)"
    assert len(result.warnings) == 1
    assert "segment_type" in result.warnings[0].path


def test_v0623_validate_coverage_pct_out_of_range_blocks() -> None:
    """coverage_pct < 0 or > 100 is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    for bad_val in (-5, 150):
        data = {"lines": [{"host": "A", "text": "x"}], "coverage_pct": bad_val}
        result = validate_script_json(data)
        assert not result.ok, f"coverage_pct={bad_val} should block"
        assert any("coverage_pct" in e.path for e in result.errors)


def test_v0623_validate_negative_retries_blocks() -> None:
    """retries < 0 is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {"lines": [{"host": "A", "text": "x"}], "retries": -1}
    result = validate_script_json(data)
    assert not result.ok
    assert any("retries" in e.path for e in result.errors)


def test_v0623_validate_wrong_type_for_title_blocks() -> None:
    """title as a non-string (e.g., a number) is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {"lines": [{"host": "A", "text": "x"}], "title": 42}
    result = validate_script_json(data)
    assert not result.ok
    assert any("title" in e.path for e in result.errors)


def test_v0623_validate_error_field_accepts_string_or_null() -> None:
    """The 'error' field accepts a string OR null (both are valid)."""
    from core.podcast.script_schema import validate_script_json

    for error_val in ("some error", None):
        data = {"lines": [{"host": "A", "text": "x"}], "error": error_val}
        result = validate_script_json(data)
        assert result.ok, f"error={error_val!r} should be valid"


def test_v0623_validate_error_field_rejects_number() -> None:
    """The 'error' field as a number (not string/null) is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    data = {"lines": [{"host": "A", "text": "x"}], "error": 42}
    result = validate_script_json(data)
    assert not result.ok
    assert any("error" in e.path for e in result.errors)


def test_v0623_validate_unknown_fields_are_accepted() -> None:
    """Unknown top-level fields are NOT errors (forward-compat: a newer
    app version may add fields an older validator doesn't know)."""
    from core.podcast.script_schema import validate_script_json

    data = {
        "lines": [{"host": "A", "text": "x"}],
        "future_field": "some value the validator doesn't know",
    }
    result = validate_script_json(data)
    assert result.ok


def test_v0623_validate_non_dict_non_list_top_level_blocks() -> None:
    """A top-level JSON value that's neither a dict nor a list (e.g., a
    string or number) is an ERROR."""
    from core.podcast.script_schema import validate_script_json

    for bad in ("just a string", 42, True):
        result = validate_script_json(bad)
        assert not result.ok, f"top-level {type(bad).__name__} should block"


def test_v0623_validate_result_ok_and_bool() -> None:
    """The .ok property is True iff no errors; bool(result) follows .ok."""
    from core.podcast.script_schema import (
        SEVERITY_ERROR,
        SEVERITY_WARNING,
        SchemaIssue,
        SchemaValidationResult,
    )

    clean = SchemaValidationResult(issues=[])
    assert clean.ok is True
    assert bool(clean) is True

    with_warning = SchemaValidationResult(
        issues=[SchemaIssue("$.x", "warn", severity=SEVERITY_WARNING)]
    )
    assert with_warning.ok is True, "warnings don't block; .ok must be True"
    assert bool(with_warning) is True

    with_error = SchemaValidationResult(issues=[SchemaIssue("$.x", "err", severity=SEVERITY_ERROR)])
    assert with_error.ok is False
    assert bool(with_error) is False


def test_v0623_schema_issue_rejects_bad_severity() -> None:
    """SchemaIssue must reject severity values outside ERROR/WARNING."""
    from core.podcast.script_schema import SchemaIssue

    with pytest.raises(ValueError, match="severity"):
        SchemaIssue(path="x", message="bad", severity="critical")  # type: ignore[arg-type]


def test_v0623_validate_script_file_loads_and_validates(tmp_path: Path) -> None:
    """validate_script_file loads a JSON file + validates it."""
    from core.podcast.script_schema import validate_script_file

    path = _write_json(tmp_path / "script.json", _valid_script_dict())
    result = validate_script_file(path)
    assert result.ok


def test_v0623_validate_script_file_missing_file_returns_error(
    tmp_path: Path,
) -> None:
    """A missing file returns a result with an ERROR (doesn't raise)."""
    from core.podcast.script_schema import validate_script_file

    result = validate_script_file(tmp_path / "nonexistent.json")
    assert not result.ok
    assert any("read" in e.message.lower() or "file" in e.message.lower() for e in result.errors)


def test_v0623_validate_script_file_bad_json_returns_error(tmp_path: Path) -> None:
    """A file with malformed JSON returns a result with an ERROR (doesn't raise)."""
    from core.podcast.script_schema import validate_script_file

    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    result = validate_script_file(path)
    assert not result.ok
    assert any("json" in e.message.lower() for e in result.errors)


def test_v0623_format_schema_for_display_has_all_fields() -> None:
    """The schema doc has all the expected field names + the header."""
    from core.podcast.script_schema import format_schema_for_display

    out = format_schema_for_display()
    assert "📋 Podcast Script JSON Schema" in out
    for field_name in (
        "lines",
        "title",
        "coverage_pct",
        "bullets_input",
        "bullets_covered",
        "bullets_missing",
        "retries",
        "forced_segments",
        "error",
    ):
        assert field_name in out, f"field {field_name!r} missing from schema doc"


def test_v0623_format_schema_for_display_log_callback() -> None:
    """The log callback is called for each output line."""
    from core.podcast.script_schema import format_schema_for_display

    logs: list[tuple[str, str]] = []
    format_schema_for_display(log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0
    assert all(level == "INFO" for _, level in logs)


def test_v0623_format_issues_clean_message() -> None:
    """A clean result's formatted output is the canonical '✅ No schema
    issues' message."""
    from core.podcast.script_schema import (
        SchemaValidationResult,
        format_issues_for_display,
    )

    out = format_issues_for_display(SchemaValidationResult(issues=[]))
    assert "✅" in out
    assert "No schema issues" in out


def test_v0623_format_issues_groups_by_severity() -> None:
    """The issue formatter groups by severity (ERROR first, then WARNING)
    with the JSON path + message."""
    from core.podcast.script_schema import (
        SEVERITY_ERROR,
        SEVERITY_WARNING,
        SchemaIssue,
        SchemaValidationResult,
        format_issues_for_display,
    )

    result = SchemaValidationResult(
        issues=[
            SchemaIssue("$.lines[0].host", "bad host", severity=SEVERITY_ERROR),
            SchemaIssue("$.lines[1].segment_type", "unknown", severity=SEVERITY_WARNING),
        ]
    )
    out = format_issues_for_display(result)
    assert "ERROR (1):" in out
    assert "WARNING (1):" in out
    assert "$.lines[0].host" in out
    assert "$.lines[1].segment_type" in out


# ── Layer 2: the CLI schema subcommand ──────────────────────────────────────


def test_v0623_cli_schema_prints_schema_doc() -> None:
    """`schema` without --validate prints the human-readable schema doc."""
    from core.podcast.cli import main as cli_main

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["schema"])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📋 Podcast Script JSON Schema" in out
    assert "lines" in out


def test_v0623_cli_schema_validate_valid_file_exits_0(tmp_path: Path) -> None:
    """`schema --validate valid.json` exits 0."""
    from core.podcast.cli import main as cli_main

    path = _write_json(tmp_path / "valid.json", _valid_script_dict())
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["schema", "--validate", str(path)])
    assert exit_code == 0
    assert "✅" in buf.getvalue()


def test_v0623_cli_schema_validate_invalid_file_exits_1(tmp_path: Path) -> None:
    """`schema --validate invalid.json` exits 1 when there are ERRORs."""
    from core.podcast.cli import main as cli_main

    bad_data = {"lines": [{"host": "C", "text": ""}]}  # bad host + empty text
    path = _write_json(tmp_path / "bad.json", bad_data)
    buf = StringIO()
    err_buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["schema", "--validate", str(path)])
    assert exit_code == 1
    assert "schema error" in err_buf.getvalue()


def test_v0623_cli_schema_validate_missing_file_exits_2(tmp_path: Path) -> None:
    """`schema --validate nonexistent.json` exits 2."""
    from core.podcast.cli import main as cli_main

    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["schema", "--validate", str(tmp_path / "nope.json")])
    assert exit_code == 2
    assert "not found" in err_buf.getvalue().lower() or "❌" in err_buf.getvalue()


def test_v0623_cli_schema_validate_bad_json_exits_1(tmp_path: Path) -> None:
    """`schema --validate bad.json` (malformed JSON) exits 1 (schema
    error, not file error)."""
    from core.podcast.cli import main as cli_main

    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    buf = StringIO()
    err_buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["schema", "--validate", str(path)])
    assert exit_code == 1
    assert "invalid JSON" in buf.getvalue() or "json" in buf.getvalue().lower()


def test_v0623_cli_schema_in_help() -> None:
    """The `schema` subcommand appears in --help alongside the others."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "schema" in result.stdout
    # The other subcommands are still there.
    for sub in ("validate", "generate", "info", "stats", "diff", "templates"):
        assert sub in result.stdout


# ── Integration: the V0.6.22 templates all pass the V0.6.23 schema ──────────


def test_v0623_integration_all_v0622_templates_pass_schema(tmp_path: Path) -> None:
    """All 6 V0.6.22 templates, when written to JSON + re-loaded, pass
    the V0.6.23 schema. This is the cross-version integration contract."""
    from core.podcast.cli import main as cli_main
    from core.podcast.script_schema import validate_script_file
    from core.podcast.script_templates import TEMPLATES

    for name in TEMPLATES:
        # Write the template via the CLI.
        out_path = tmp_path / f"{name}.json"
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            cli_main(["templates", "--name", name, "--out", str(out_path)])
        assert out_path.exists(), f"Template {name!r} wasn't written"
        # Validate via the schema.
        result = validate_script_file(out_path)
        assert result.ok, (
            f"Template {name!r} failed the V0.6.23 schema: "
            f"{[(e.path, e.message) for e in result.errors]}"
        )


def test_v0623_integration_template_then_schema_validate_via_cli(
    tmp_path: Path,
) -> None:
    """Integration: template → schema --validate passes (the CLI's own
    schema subcommand accepts the CLI's own template output)."""
    from core.podcast.cli import main as cli_main

    # Step 1: write a template.
    tmpl_path = tmp_path / "qa.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "qa_format", "--out", str(tmpl_path)])
    assert tmpl_path.exists()

    # Step 2: schema --validate it.
    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(["schema", "--validate", str(tmpl_path)])
    assert exit_code == 0, (
        f"Template-derived script failed schema validation; output:\n{buf2.getvalue()}"
    )
