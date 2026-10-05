"""V0.6.24 — the to_json / from_json round-trip bug-fix pins.

This file pins the V0.6.24 bug fix:

THE BUG (discovered during the V0.6.23 schema round)
----------------------------------------------------
Before V0.6.24, ``ScriptResult.to_json()`` serialized only 4 fields
(lines, coverage_pct, bullets_covered, bullets_missing) and DROPPED
title, bullets_input, retries, forced_segments, error. And
``ScriptResult.from_json()`` ALSO dropped title, retries,
forced_segments, error when reading (it read bullets_input but
to_json didn't serialize it, so it was lost in the round-trip anyway).

The wizard's "Export Script" → "Import Script" round-trip LOST:
  - title (the imported script got a timestamp filename instead of
    the original title)
  - bullets_input (the anti-hallucination audit trail was lost)
  - retries / forced_segments (the script's provenance was lost)
  - error (any generation error message was lost)

THE FIX (W-j1)
--------------
Both methods now handle all 9 fields:
  - ``to_json`` serializes: lines, title, coverage_pct, bullets_input,
    bullets_covered, bullets_missing, retries, forced_segments, error.
  - ``from_json`` reads: lines, title, bullets_input, bullets_covered,
    bullets_missing, coverage_pct, retries, forced_segments, error.

The defaults (title="", retries=0, forced_segments=0, error=None)
preserve backward-compat for old JSON files that don't have these
fields. The V0.6.23 schema module documents the full expected format;
this fix makes to_json match it.

THE PINS (this file)
--------------------
Layer 1: round-trip preservation — every field survives to_json →
from_json → to_json → from_json.
Layer 2: backward-compat — old JSON files (without the new fields)
still load with sensible defaults.
Layer 3: the V0.6.23 schema accepts the V0.6.24 to_json output (the
cross-version integration contract).
Layer 4: the V0.6.22 templates' to_json output passes the V0.6.23
schema (the templates still work after the fix).

All tests are pure-Python (no PySide6 / no torch).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── helpers ────────────────────────────────────────────────────────────────


def _make_full_script():
    """A ScriptResult with ALL fields populated (the round-trip target)."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    return ScriptResult(
        lines=[
            ScriptLine(host="A", text="intro line", source_ref="r1", segment_type="intro"),
            ScriptLine(host="B", text="body line", source_ref="r2", segment_type="content"),
            ScriptLine(
                host="A", text="conclusion line", source_ref="r3", segment_type="conclusion"
            ),
        ],
        bullets_input=["bullet 1", "bullet 2", "bullet 3"],
        bullets_covered=[0, 2],
        bullets_missing=[1],
        coverage_pct=66.6,
        retries=2,
        forced_segments=1,
        error="some generation error",
        title="My Full Test Podcast",
    )


def _make_minimal_script():
    """A ScriptResult with only the required fields (defaults for the rest)."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    return ScriptResult(
        lines=[ScriptLine(host="A", text="just one line", source_ref="r", segment_type="intro")],
    )


# ── Layer 1: round-trip preservation ───────────────────────────────────────


def test_v0624_round_trip_preserves_title() -> None:
    """The title field survives to_json → from_json."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.title == original.title == "My Full Test Podcast"


def test_v0624_round_trip_preserves_bullets_input() -> None:
    """The bullets_input field survives the round-trip (the anti-hallucination
    audit trail is preserved)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.bullets_input == original.bullets_input == ["bullet 1", "bullet 2", "bullet 3"]


def test_v0624_round_trip_preserves_bullets_covered() -> None:
    """The bullets_covered field survives the round-trip."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.bullets_covered == original.bullets_covered == [0, 2]


def test_v0624_round_trip_preserves_bullets_missing() -> None:
    """The bullets_missing field survives the round-trip."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.bullets_missing == original.bullets_missing == [1]


def test_v0624_round_trip_preserves_coverage_pct() -> None:
    """The coverage_pct field survives the round-trip."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.coverage_pct == original.coverage_pct == pytest.approx(66.6)


def test_v0624_round_trip_preserves_retries() -> None:
    """The retries field survives the round-trip (the script's provenance
    is preserved)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.retries == original.retries == 2


def test_v0624_round_trip_preserves_forced_segments() -> None:
    """The forced_segments field survives the round-trip."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.forced_segments == original.forced_segments == 1


def test_v0624_round_trip_preserves_error() -> None:
    """The error field survives the round-trip (the generation error
    message is preserved)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert restored.error == original.error == "some generation error"


def test_v0624_round_trip_preserves_error_none() -> None:
    """The error field survives the round-trip when it's None (the common
    case — no generation error)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_minimal_script()  # error defaults to None
    restored = ScriptResult.from_json(original.to_json())
    assert restored.error is None
    assert restored.error == original.error


def test_v0624_round_trip_preserves_lines() -> None:
    """The lines field survives the round-trip (all line fields preserved)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    restored = ScriptResult.from_json(original.to_json())
    assert len(restored.lines) == len(original.lines)
    for orig, rest in zip(original.lines, restored.lines, strict=False):
        assert orig.host == rest.host
        assert orig.text == rest.text
        assert orig.source_ref == rest.source_ref
        assert orig.segment_type == rest.segment_type


def test_v0624_double_round_trip_is_idempotent() -> None:
    """to_json → from_json → to_json → from_json produces the same result
    both times (the round-trip is idempotent — no data drifts on repeat)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_full_script()
    first_round = ScriptResult.from_json(original.to_json())
    second_round = ScriptResult.from_json(first_round.to_json())

    # Every field should match across all three.
    for field_name in (
        "title",
        "bullets_input",
        "bullets_covered",
        "bullets_missing",
        "coverage_pct",
        "retries",
        "forced_segments",
        "error",
    ):
        orig_val = getattr(original, field_name)
        first_val = getattr(first_round, field_name)
        second_val = getattr(second_round, field_name)
        assert orig_val == first_val == second_val, (
            f"field {field_name!r} drifted: orig={orig_val!r} "
            f"first={first_val!r} second={second_val!r}"
        )


def test_v0624_to_json_output_has_all_nine_fields() -> None:
    """The to_json output must include all 9 documented fields (the
    V0.6.23 schema contract)."""

    script = _make_full_script()
    data = json.loads(script.to_json())
    expected_keys = {
        "lines",
        "title",
        "coverage_pct",
        "bullets_input",
        "bullets_covered",
        "bullets_missing",
        "retries",
        "forced_segments",
        "error",
    }
    assert set(data.keys()) == expected_keys, (
        f"to_json output keys mismatch. Expected: {expected_keys}. "
        f"Got: {set(data.keys())}. Missing: {expected_keys - set(data.keys())}. "
        f"Extra: {set(data.keys()) - expected_keys}."
    )


# ── Layer 2: backward-compat (old JSON files still load) ────────────────────


def test_v0624_from_json_old_format_without_title_loads() -> None:
    """An old JSON file without 'title' still loads (defaults to '')."""
    from core.podcast.script_generator import ScriptResult

    old_json = json.dumps(
        {
            "lines": [{"host": "A", "text": "hello", "source_ref": "r", "segment_type": "intro"}],
            "coverage_pct": 100.0,
            "bullets_covered": [0],
            "bullets_missing": [],
        }
    )
    script = ScriptResult.from_json(old_json)
    assert script.title == ""  # default
    assert len(script.lines) == 1


def test_v0624_from_json_old_format_without_retries_loads() -> None:
    """An old JSON file without 'retries' still loads (defaults to 0)."""
    from core.podcast.script_generator import ScriptResult

    old_json = json.dumps(
        {
            "lines": [{"host": "A", "text": "hello", "source_ref": "r", "segment_type": "intro"}],
        }
    )
    script = ScriptResult.from_json(old_json)
    assert script.retries == 0  # default
    assert script.forced_segments == 0  # default
    assert script.error is None  # default
    assert script.bullets_input == []  # default


def test_v0624_from_json_new_format_with_all_fields_loads() -> None:
    """A new V0.6.24 JSON file with all 9 fields loads correctly."""
    from core.podcast.script_generator import ScriptResult

    new_json = json.dumps(
        {
            "lines": [{"host": "A", "text": "hello", "source_ref": "r", "segment_type": "intro"}],
            "title": "New Format",
            "coverage_pct": 75.0,
            "bullets_input": ["b1"],
            "bullets_covered": [0],
            "bullets_missing": [],
            "retries": 3,
            "forced_segments": 2,
            "error": "an error",
        }
    )
    script = ScriptResult.from_json(new_json)
    assert script.title == "New Format"
    assert script.coverage_pct == 75.0
    assert script.bullets_input == ["b1"]
    assert script.retries == 3
    assert script.forced_segments == 2
    assert script.error == "an error"


def test_v0624_from_json_error_null_loads_as_none() -> None:
    """A JSON file with error: null loads as error=None."""
    from core.podcast.script_generator import ScriptResult

    json_str = json.dumps(
        {
            "lines": [{"host": "A", "text": "x", "source_ref": "r", "segment_type": "intro"}],
            "error": None,
        }
    )
    script = ScriptResult.from_json(json_str)
    assert script.error is None


def test_v0624_from_json_raw_array_shorthand_still_works() -> None:
    """The raw-array shorthand (a top-level JSON array of line objects)
    still works after the fix (from_json accepts it; the meta fields
    default)."""
    from core.podcast.script_generator import ScriptResult

    raw_array = json.dumps(
        [
            {"host": "A", "text": "line 1", "source_ref": "r", "segment_type": "intro"},
            {"host": "B", "text": "line 2", "source_ref": "r", "segment_type": "content"},
        ]
    )
    script = ScriptResult.from_json(raw_array)
    assert len(script.lines) == 2
    assert script.title == ""  # default (no meta in raw-array form)
    assert script.retries == 0  # default


# ── Layer 3: the V0.6.23 schema accepts the V0.6.24 to_json output ──────────


def test_v0624_to_json_output_passes_v0623_schema() -> None:
    """The V0.6.24 to_json output must pass the V0.6.23 schema (the
    cross-version integration contract — the schema was written against
    the FULL format, and V0.6.24 makes to_json match it)."""
    from core.podcast.script_schema import validate_script_json

    script = _make_full_script()
    data = json.loads(script.to_json())
    result = validate_script_json(data)
    assert result.ok, (
        f"V0.6.24 to_json output failed the V0.6.23 schema: "
        f"{[(e.path, e.message) for e in result.errors]}"
    )


def test_v0624_to_json_output_with_error_field_passes_schema() -> None:
    """A script with error='some error' (a string) must pass the schema
    (the schema accepts string-or-null for the error field)."""
    from core.podcast.script_schema import validate_script_json

    script = _make_full_script()  # has error='some generation error'
    data = json.loads(script.to_json())
    assert data["error"] == "some generation error"
    result = validate_script_json(data)
    assert result.ok


# ── Layer 4: the V0.6.22 templates still work after the fix ────────────────


def test_v0624_v0622_templates_to_json_output_passes_schema() -> None:
    """All 6 V0.6.22 templates' to_json output must pass the V0.6.23 schema
    after the V0.6.24 fix (the templates still produce valid JSON)."""
    from core.podcast.script_schema import validate_script_json
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        data = json.loads(template.script.to_json())
        result = validate_script_json(data)
        assert result.ok, (
            f"Template {name!r} to_json output failed the schema after the "
            f"V0.6.24 fix: {[(e.path, e.message) for e in result.errors]}"
        )


def test_v0624_v0622_templates_round_trip_preserves_title() -> None:
    """The V0.6.22 templates' titles survive the V0.6.24 round-trip
    (before V0.6.24, the title was LOST — a real bug for the templates
    which all have descriptive titles like 'Lecture Podcast (Template)')."""
    from core.podcast.script_generator import ScriptResult
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        original = template.script
        restored = ScriptResult.from_json(original.to_json())
        assert restored.title == original.title, (
            f"Template {name!r}: title drifted in round-trip: "
            f"orig={original.title!r} restored={restored.title!r}"
        )


# ── Layer 5: the V0.6.19-V0.6.22 CLI still works after the fix ─────────────


def test_v0624_cli_info_subcommand_still_works(tmp_path: Path) -> None:
    """The V0.6.19 CLI's `info` subcommand still works on V0.6.24 to_json
    output (the _load_script_json helper calls from_json)."""
    from core.podcast.cli import main as cli_main

    script = _make_full_script()
    path = tmp_path / "full.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["info", "--script", str(path)])
    assert exit_code == 0


def test_v0624_cli_stats_subcommand_still_works(tmp_path: Path) -> None:
    """The V0.6.20 CLI's `stats` subcommand still works on V0.6.24 to_json
    output."""
    from core.podcast.cli import main as cli_main

    script = _make_full_script()
    path = tmp_path / "full.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["stats", "--script", str(path), "--json"])
    assert exit_code == 0


def test_v0624_cli_validate_subcommand_still_works(tmp_path: Path) -> None:
    """The V0.6.19 CLI's `validate` subcommand still works on V0.6.24
    to_json output."""
    from core.podcast.cli import main as cli_main

    script = _make_full_script()
    path = tmp_path / "full.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["validate", "--script", str(path), "--voice-a", "va", "--voice-b", "vb"])
    assert exit_code == 0


def test_v0624_cli_schema_subcommand_validates_v0624_output(
    tmp_path: Path,
) -> None:
    """The V0.6.23 CLI's `schema --validate` subcommand accepts the V0.6.24
    to_json output (the cross-version integration contract)."""
    from core.podcast.cli import main as cli_main

    script = _make_full_script()
    path = tmp_path / "full.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["schema", "--validate", str(path)])
    assert exit_code == 0


def test_v0624_cli_diff_subcommand_works_with_v0624_output(
    tmp_path: Path,
) -> None:
    """The V0.6.21 CLI's `diff` subcommand works on V0.6.24 to_json output
    (the diff between two V0.6.24-serialized scripts)."""
    from core.podcast.cli import main as cli_main
    from core.podcast.script_generator import ScriptLine, ScriptResult

    script_a = _make_full_script()
    script_b = ScriptResult(
        lines=script_a.lines
        + [ScriptLine(host="B", text="extra line", source_ref="r4", segment_type="content")],
        title=script_a.title,
        bullets_input=script_a.bullets_input,
        bullets_covered=script_a.bullets_covered,
        bullets_missing=script_a.bullets_missing,
        coverage_pct=script_a.coverage_pct,
        retries=script_a.retries,
        forced_segments=script_a.forced_segments,
        error=script_a.error,
    )
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text(script_a.to_json(), encoding="utf-8")
    path_b.write_text(script_b.to_json(), encoding="utf-8")

    exit_code = cli_main(
        ["diff", "--script-a", str(path_a), "--script-b", str(path_b), "--summary-only"]
    )
    assert exit_code == 0


# ── Layer 6: the existing V0.6.0 e2e test contract still holds ─────────────


def test_v0624_existing_e2e_test_contract_still_holds() -> None:
    """The existing test_0600_tool_transcribe_podcast_e2e test at line 379-384
    asserts: data['lines'] host values + data['coverage_pct'] + the
    round-trip preserves lines text + coverage_pct. This test pins that
    the V0.6.24 fix doesn't break those existing assertions."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    # Build a script like the e2e test does.
    r = ScriptResult(
        lines=[
            ScriptLine(host="A", text="line 1", source_ref="r", segment_type="intro"),
            ScriptLine(host="B", text="line 2", source_ref="r", segment_type="content"),
            ScriptLine(host="A", text="line 3", source_ref="r", segment_type="conclusion"),
        ],
        coverage_pct=1.0,
    )
    data = json.loads(r.to_json())
    # The e2e test's assertions:
    assert [ln["host"] for ln in data["lines"]] == ["A", "B", "A"]
    assert data["coverage_pct"] == 1.0
    r2 = type(r).from_json(r.to_json())
    assert [ln.text for ln in r2.lines] == [ln.text for ln in r.lines]
    assert r2.coverage_pct == 1.0
