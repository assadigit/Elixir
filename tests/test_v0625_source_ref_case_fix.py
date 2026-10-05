"""V0.6.25 — the source_ref case-preservation bug-fix pins.

This file pins the V0.6.25 bug fix — the SECOND round-trip bug found
during the audit the V0.6.24 worklog recommended:

THE BUG (discovered during the V0.6.24 audit)
---------------------------------------------
Before V0.6.25, ``ScriptResult.from_json()`` did
``str(obj.get("source_ref", "")).strip().lower()`` — it SILENTLY
LOWERCASED the source_ref on read. ``to_json`` writes source_ref
verbatim, so the round-trip through to_json → from_json mangled
mixed-case source refs (e.g., "MySource_Chapter3" →
"mysource_chapter3").

The .lower() was added in the V0.6.0 lint triage commit (bf994fa)
without a documented reason; no tests rely on it. Removing it makes
the round-trip lossless.

THE FIX (W-j2, core/podcast/script_generator.py)
-------------------------------------------------
``from_json`` now does ``.strip()`` only (no ``.lower()``). The
round-trip preserves mixed-case source_ref values verbatim.

THE PINS (this file)
--------------------
Layer 1: round-trip case preservation — mixed-case source_ref
survives to_json → from_json.
Layer 2: backward-compat — lowercase source_ref (the V0.6.0-v0.6.24
canonical form) still loads correctly (no change for the common case).
Layer 3: the V0.6.21 diff's source_ref-ignored contract still holds
(the diff treats source_ref changes as non-modifications; the case
fix doesn't affect this).
Layer 4: the V0.6.23 schema accepts the V0.6.25 to_json output.
Layer 5: the V0.6.22 templates' source_refs survive the round-trip
(the templates use lowercase source_refs so this is a no-op for
them, but the test pins the contract).

All tests are pure-Python (no PySide6 / no torch).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── helpers ────────────────────────────────────────────────────────────────


def _make_mixed_case_script():
    """A ScriptResult with mixed-case source_ref values (the bug target)."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    return ScriptResult(
        lines=[
            ScriptLine(
                host="A",
                text="intro line",
                source_ref="MySource_Chapter3",
                segment_type="intro",
            ),
            ScriptLine(
                host="B",
                text="body line",
                source_ref="Ref_2_MixedCase",
                segment_type="content",
            ),
            ScriptLine(
                host="A",
                text="conclusion line",
                source_ref="Conclusion_Ref",
                segment_type="conclusion",
            ),
        ],
        title="Mixed-Case source_ref Test",
    )


# ── Layer 1: round-trip case preservation ───────────────────────────────────


def test_v0625_round_trip_preserves_mixed_case_source_ref() -> None:
    """A mixed-case source_ref survives to_json → from_json verbatim."""
    from core.podcast.script_generator import ScriptResult

    original = _make_mixed_case_script()
    restored = ScriptResult.from_json(original.to_json())
    for orig_line, rest_line in zip(original.lines, restored.lines, strict=False):
        assert orig_line.source_ref == rest_line.source_ref, (
            f"source_ref case was mangled: orig={orig_line.source_ref!r} "
            f"restored={rest_line.source_ref!r}"
        )


def test_v0625_round_trip_preserves_uppercase_source_ref() -> None:
    """An ALL-UPPERCASE source_ref (e.g., 'BULLET_1') survives the
    round-trip — before V0.6.25 it was lowercased to 'bullet_1'."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    original = ScriptResult(
        lines=[
            ScriptLine(host="A", text="x", source_ref="BULLET_1", segment_type="intro"),
        ],
    )
    restored = ScriptResult.from_json(original.to_json())
    assert restored.lines[0].source_ref == "BULLET_1", (
        f"UPPERCASE source_ref was lowercased: got {restored.lines[0].source_ref!r}"
    )


def test_v0625_round_trip_preserves_camel_case_source_ref() -> None:
    """A camelCase source_ref (e.g., 'mySourceRef') survives the round-trip."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    original = ScriptResult(
        lines=[
            ScriptLine(host="A", text="x", source_ref="mySourceRef", segment_type="intro"),
        ],
    )
    restored = ScriptResult.from_json(original.to_json())
    assert restored.lines[0].source_ref == "mySourceRef"


def test_v0625_round_trip_preserves_source_ref_with_spaces() -> None:
    """A source_ref with spaces (e.g., 'Chapter 3 Summary') survives
    the round-trip (the .strip() only trims leading/trailing whitespace;
    internal spaces are preserved)."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    original = ScriptResult(
        lines=[
            ScriptLine(host="A", text="x", source_ref="Chapter 3 Summary", segment_type="intro"),
        ],
    )
    restored = ScriptResult.from_json(original.to_json())
    assert restored.lines[0].source_ref == "Chapter 3 Summary"


def test_v0625_round_trip_strips_leading_trailing_whitespace_in_source_ref() -> None:
    """The .strip() on source_ref is preserved (leading/trailing
    whitespace is trimmed) — this is a normalization, not a data loss."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    original = ScriptResult(
        lines=[
            ScriptLine(host="A", text="x", source_ref="  spaced  ", segment_type="intro"),
        ],
    )
    restored = ScriptResult.from_json(original.to_json())
    assert restored.lines[0].source_ref == "spaced"  # stripped, not lowercased


def test_v0625_double_round_trip_preserves_mixed_case() -> None:
    """to_json → from_json → to_json → from_json preserves mixed-case
    source_ref both times (idempotent)."""
    from core.podcast.script_generator import ScriptResult

    original = _make_mixed_case_script()
    first_round = ScriptResult.from_json(original.to_json())
    second_round = ScriptResult.from_json(first_round.to_json())
    for i, (orig, first, second) in enumerate(
        zip(original.lines, first_round.lines, second_round.lines, strict=False)
    ):
        assert orig.source_ref == first.source_ref == second.source_ref, (
            f"Line {i}: source_ref drifted across double round-trip: "
            f"orig={orig.source_ref!r} first={first.source_ref!r} "
            f"second={second.source_ref!r}"
        )


# ── Layer 2: backward-compat (lowercase source_ref still loads) ─────────────


def test_v0625_lowercase_source_ref_still_loads() -> None:
    """A lowercase source_ref (the V0.6.0-V0.6.24 canonical form) still
    loads correctly — the fix doesn't break the common case."""
    from core.podcast.script_generator import ScriptResult

    json_str = json.dumps(
        {
            "lines": [
                {"host": "A", "text": "x", "source_ref": "bullet 1", "segment_type": "intro"},
                {"host": "B", "text": "y", "source_ref": "bullet 2", "segment_type": "content"},
            ],
        }
    )
    script = ScriptResult.from_json(json_str)
    assert script.lines[0].source_ref == "bullet 1"
    assert script.lines[1].source_ref == "bullet 2"


def test_v0625_empty_source_ref_still_loads_as_empty() -> None:
    """An empty source_ref still loads as empty (the default)."""
    from core.podcast.script_generator import ScriptResult

    json_str = json.dumps(
        {
            "lines": [{"host": "A", "text": "x", "source_ref": "", "segment_type": "intro"}],
        }
    )
    script = ScriptResult.from_json(json_str)
    assert script.lines[0].source_ref == ""


def test_v0625_missing_source_ref_still_loads_as_empty() -> None:
    """A line without a source_ref field still loads with source_ref=''
    (the default — from_json's obj.get('source_ref', '') handles it)."""
    from core.podcast.script_generator import ScriptResult

    json_str = json.dumps(
        {
            "lines": [{"host": "A", "text": "x", "segment_type": "intro"}],
        }
    )
    script = ScriptResult.from_json(json_str)
    assert script.lines[0].source_ref == ""


# ── Layer 3: the V0.6.21 diff's source_ref-ignored contract still holds ─────


def test_v0625_v0621_diff_source_ref_change_still_ignored() -> None:
    """The V0.6.21 diff's contract: a source_ref change ALONE is NOT a
    line modification. The V0.6.25 case fix doesn't affect this (the
    diff compares source_ref values directly, case-sensitively, but a
    pure source_ref change is still ignored by the diff's _line_signature)."""
    from core.podcast.script_diff import diff_scripts
    from core.podcast.script_generator import ScriptLine, ScriptResult

    before = ScriptResult(
        lines=[ScriptLine(host="A", text="same", source_ref="ref1", segment_type="intro")]
    )
    after = ScriptResult(
        lines=[ScriptLine(host="A", text="same", source_ref="ref2", segment_type="intro")]
    )
    diff = diff_scripts(before, after)
    assert diff.is_clean is True
    assert diff.equal_count == 1


def test_v0625_v0621_diff_source_ref_case_change_still_ignored() -> None:
    """A source_ref CASE change alone (e.g., 'Ref1' → 'REF1') is still
    NOT a line modification — the diff ignores source_ref entirely
    (it's metadata, not content). The V0.6.25 case fix doesn't change
    this contract."""
    from core.podcast.script_diff import diff_scripts
    from core.podcast.script_generator import ScriptLine, ScriptResult

    before = ScriptResult(
        lines=[ScriptLine(host="A", text="same", source_ref="Ref1", segment_type="intro")]
    )
    after = ScriptResult(
        lines=[ScriptLine(host="A", text="same", source_ref="REF1", segment_type="intro")]
    )
    diff = diff_scripts(before, after)
    # The diff ignores source_ref entirely (the V0.6.21 contract), so a
    # case change in source_ref is NOT a modification.
    assert diff.is_clean is True


# ── Layer 4: the V0.6.23 schema accepts the V0.6.25 to_json output ──────────


def test_v0625_to_json_output_with_mixed_case_source_ref_passes_schema() -> None:
    """The V0.6.25 to_json output (with mixed-case source_ref) must
    pass the V0.6.23 schema (the schema accepts any string for
    source_ref — no case constraint)."""
    from core.podcast.script_schema import validate_script_json

    script = _make_mixed_case_script()
    data = json.loads(script.to_json())
    result = validate_script_json(data)
    assert result.ok, (
        f"V0.6.25 to_json output with mixed-case source_ref failed the "
        f"V0.6.23 schema: {[(e.path, e.message) for e in result.errors]}"
    )


# ── Layer 5: the V0.6.22 templates' source_refs survive the round-trip ─────


def test_v0625_v0622_templates_source_refs_survive_round_trip() -> None:
    """All 6 V0.6.22 templates' source_refs survive the V0.6.25
    round-trip. The templates use lowercase source_refs (e.g., 'intro',
    'content', 'q1') so this is a no-op for them, but the test pins the
    contract — if a future template uses a mixed-case source_ref, the
    round-trip must preserve it."""
    from core.podcast.script_generator import ScriptResult
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        original = template.script
        restored = ScriptResult.from_json(original.to_json())
        for i, (orig, rest) in enumerate(zip(original.lines, restored.lines, strict=False)):
            assert orig.source_ref == rest.source_ref, (
                f"Template {name!r} line {i}: source_ref drifted in "
                f"round-trip: orig={orig.source_ref!r} restored={rest.source_ref!r}"
            )


# ── Layer 6: the CLI subcommands still work with mixed-case source_ref ────


def test_v0625_cli_info_subcommand_works_with_mixed_case_source_ref(
    tmp_path: Path,
) -> None:
    """The V0.6.19 CLI's `info` subcommand works on a script with
    mixed-case source_ref (no crash, exit 0)."""
    from core.podcast.cli import main as cli_main

    script = _make_mixed_case_script()
    path = tmp_path / "mixed.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["info", "--script", str(path)])
    assert exit_code == 0


def test_v0625_cli_validate_subcommand_works_with_mixed_case_source_ref(
    tmp_path: Path,
) -> None:
    """The V0.6.19 CLI's `validate` subcommand works on a script with
    mixed-case source_ref."""
    from core.podcast.cli import main as cli_main

    script = _make_mixed_case_script()
    path = tmp_path / "mixed.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["validate", "--script", str(path), "--voice-a", "va", "--voice-b", "vb"])
    assert exit_code == 0


def test_v0625_cli_stats_subcommand_works_with_mixed_case_source_ref(
    tmp_path: Path,
) -> None:
    """The V0.6.20 CLI's `stats` subcommand works on a script with
    mixed-case source_ref."""
    from core.podcast.cli import main as cli_main

    script = _make_mixed_case_script()
    path = tmp_path / "mixed.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["stats", "--script", str(path), "--json"])
    assert exit_code == 0


def test_v0625_cli_schema_subcommand_validates_mixed_case_source_ref(
    tmp_path: Path,
) -> None:
    """The V0.6.23 CLI's `schema --validate` accepts a script with
    mixed-case source_ref."""
    from core.podcast.cli import main as cli_main

    script = _make_mixed_case_script()
    path = tmp_path / "mixed.json"
    path.write_text(script.to_json(), encoding="utf-8")

    exit_code = cli_main(["schema", "--validate", str(path)])
    assert exit_code == 0
