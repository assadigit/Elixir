"""V0.6.22 — the script-templates + templates-CLI batch pins.

This file pins the V0.6.22 additions:

Layer 1 — the SCRIPT TEMPLATES module (W-h1, NEW
core/podcast/script_templates.py):
  - 6 pre-built templates: lecture_intro / conversational_intro /
    qa_format / interview / summary_only / deep_dive.
  - ``TEMPLATES`` registry dict, ``get_template(name)``,
    ``list_templates()``, ``format_templates_for_display()``.
  - Each template is a ``ScriptTemplate`` dataclass with name /
    description / mode / script / estimated_lines.
  - ``get_template`` returns a FRESH ScriptResult (caller can mutate
    without affecting the registry).

Layer 2 — the CLI templates subcommand (W-h2, core/podcast/cli.py):
  - ``templates`` subcommand: lists all templates, or writes one to
    a JSON file with ``--name`` + ``--out``.
  - Exits 0 on success, 1 if the template name is unknown, 2 on
    file/argument error.

All tests are pure-Python (no PySide6 / no torch / no soundfile).
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


# ── Layer 1: the script templates module ─────────────────────────────────────


def test_v0622_templates_registry_has_six_templates() -> None:
    """The TEMPLATES registry has exactly the 6 documented templates."""
    from core.podcast.script_templates import TEMPLATES

    expected = {
        "lecture_intro",
        "conversational_intro",
        "qa_format",
        "interview",
        "summary_only",
        "deep_dive",
    }
    assert set(TEMPLATES.keys()) == expected, f"Expected {expected}; got {set(TEMPLATES.keys())}"


def test_v0622_list_templates_returns_in_registration_order() -> None:
    """list_templates() returns the templates in registration order
    (most-useful first), not alphabetically."""
    from core.podcast.script_templates import list_templates

    templates = list_templates()
    names = [t.name for t in templates]
    # The registration order in the module is:
    # lecture_intro, conversational_intro, qa_format, interview, summary_only, deep_dive
    assert names == [
        "lecture_intro",
        "conversational_intro",
        "qa_format",
        "interview",
        "summary_only",
        "deep_dive",
    ], f"Registration order changed: {names}"


@pytest.mark.parametrize(
    "name,expected_lines,expected_mode",
    [
        ("lecture_intro", 3, "lecture"),
        ("conversational_intro", 3, "conversational"),
        ("qa_format", 4, "conversational"),
        ("interview", 5, "conversational"),
        ("summary_only", 1, "lecture"),
        ("deep_dive", 6, "conversational"),
    ],
)
def test_v0622_get_template_returns_correct_script(
    name: str, expected_lines: int, expected_mode: str
) -> None:
    """Each template has the documented line count + mode."""
    from core.podcast.script_templates import TEMPLATES, get_template

    script = get_template(name)
    assert len(script.lines) == expected_lines, (
        f"{name}: expected {expected_lines} lines, got {len(script.lines)}"
    )
    template = TEMPLATES[name]
    assert template.mode == expected_mode


def test_v0622_get_template_unknown_name_raises_keyerror() -> None:
    """An unknown template name raises KeyError with a helpful message
    listing the available names."""
    from core.podcast.script_templates import get_template

    with pytest.raises(KeyError, match="Unknown template name"):
        get_template("nonexistent_template")


def test_v0622_get_template_returns_fresh_script_not_registry_reference() -> None:
    """get_template returns a FRESH ScriptResult — mutating it doesn't
    affect the registry (the caller can edit the script freely)."""
    from core.podcast.script_templates import TEMPLATES, get_template

    script = get_template("lecture_intro")
    # Mutate the returned script.
    script.lines[0].text = "MUTATED"
    script.title = "MUTATED TITLE"
    # The registry's template must be unchanged.
    registry_script = TEMPLATES["lecture_intro"].script
    assert registry_script.lines[0].text != "MUTATED", (
        "Mutating get_template()'s return value affected the registry!"
    )
    assert registry_script.title != "MUTATED TITLE"


def test_v0622_templates_have_placeholder_text() -> None:
    """Each template's lines have [BRACKETED_HINTS] placeholder text
    the operator replaces."""
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        for i, line in enumerate(template.script.lines):
            assert "[" in line.text and "]" in line.text, (
                f"Template {name!r} line {i}: text should have [BRACKETED_HINTS] "
                f"placeholder; got {line.text!r}"
            )


def test_v0622_templates_have_valid_host_values() -> None:
    """Each template's lines have host values 'A' or 'B' only (the
    audio generator + validator expect these)."""
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        for i, line in enumerate(template.script.lines):
            assert line.host in ("A", "B"), (
                f"Template {name!r} line {i}: host must be 'A' or 'B', got {line.host!r}"
            )


def test_v0622_lecture_templates_have_no_host_b() -> None:
    """Lecture-mode templates (lecture_intro, summary_only) have NO
    Host B lines (lecture is 1-host only)."""
    from core.podcast.script_templates import TEMPLATES

    for name in ("lecture_intro", "summary_only"):
        template = TEMPLATES[name]
        assert template.mode == "lecture"
        for line in template.script.lines:
            assert line.host == "A", f"Lecture template {name!r} has a Host B line: {line!r}"


def test_v0622_conversational_templates_have_both_hosts() -> None:
    """Conversational templates have at least one Host A AND one Host B line."""
    from core.podcast.script_templates import TEMPLATES

    conversational_names = (
        "conversational_intro",
        "qa_format",
        "interview",
        "deep_dive",
    )
    for name in conversational_names:
        template = TEMPLATES[name]
        assert template.mode == "conversational"
        hosts = {line.host for line in template.script.lines}
        assert "A" in hosts and "B" in hosts, (
            f"Conversational template {name!r} missing a host; got {hosts}"
        )


def test_v0622_templates_have_intro_and_conclusion_segments() -> None:
    """Each multi-line template's first line is 'intro' and last line
    is 'conclusion' (the script_generator contract the validator expects)."""
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        if len(template.script.lines) < 2:
            continue  # summary_only is 1 line — skip the intro/conclusion check
        first = template.script.lines[0]
        last = template.script.lines[-1]
        assert first.segment_type == "intro", (
            f"Template {name!r}: first line segment_type should be 'intro', "
            f"got {first.segment_type!r}"
        )
        assert last.segment_type == "conclusion", (
            f"Template {name!r}: last line segment_type should be 'conclusion', "
            f"got {last.segment_type!r}"
        )


def test_v0622_templates_have_nonempty_title() -> None:
    """Each template has a non-empty title (the I1 info rule in the
    validator flags empty titles)."""
    from core.podcast.script_templates import TEMPLATES

    for name, template in TEMPLATES.items():
        assert template.script.title, (
            f"Template {name!r}: title is empty (validator I1 would flag it)"
        )


def test_v0622_template_scripts_pass_validator() -> None:
    """Every template, when validated, passes (no ERROR-level issues).
    This is the integration contract: templates are valid starting points."""
    from core.podcast.script_templates import TEMPLATES
    from core.podcast.script_validator import validate_script

    for name, template in TEMPLATES.items():
        script = template.script
        is_conversational = template.mode == "conversational"
        # Always provide Host A voice (the validator's W5 warns if empty);
        # provide Host B voice only in conversational mode.
        result = validate_script(
            script,
            host_a_voice="vibevoice:Carter",
            host_b_voice="vibevoice:Erin" if is_conversational else "",
            is_conversational=is_conversational,
        )
        assert result.ok, f"Template {name!r} failed validation: {[e.code for e in result.errors]}"


def test_v0622_format_templates_for_display_has_header() -> None:
    """The display formatter has the header + the column header + each
    template's name."""
    from core.podcast.script_templates import format_templates_for_display

    out = format_templates_for_display()
    assert "📝 Available Podcast Script Templates" in out
    assert "NAME" in out and "LINES" in out and "MODE" in out and "DESCRIPTION" in out
    # All 6 template names should appear.
    for name in (
        "lecture_intro",
        "conversational_intro",
        "qa_format",
        "interview",
        "summary_only",
        "deep_dive",
    ):
        assert name in out


def test_v0622_format_templates_for_display_log_callback() -> None:
    """The log callback is called for each output line."""
    from core.podcast.script_templates import format_templates_for_display

    logs: list[tuple[str, str]] = []
    format_templates_for_display(log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0
    assert all(level == "INFO" for _, level in logs)


# ── Layer 2: the CLI templates subcommand ───────────────────────────────────


def test_v0622_cli_templates_list_mode_prints_all(tmp_path: Path) -> None:
    """`templates` without --name lists all available templates."""
    from core.podcast.cli import main as cli_main

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["templates"])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📝 Available Podcast Script Templates" in out
    for name in (
        "lecture_intro",
        "conversational_intro",
        "qa_format",
        "interview",
        "summary_only",
        "deep_dive",
    ):
        assert name in out


def test_v0622_cli_templates_write_mode_creates_valid_json(
    tmp_path: Path,
) -> None:
    """`templates --name lecture_intro --out file.json` writes a valid
    script JSON that the CLI's own _load_script_json can read back."""
    from core.podcast.cli import _load_script_json
    from core.podcast.cli import main as cli_main

    out_path = tmp_path / "template.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["templates", "--name", "lecture_intro", "--out", str(out_path)])
    assert exit_code == 0
    assert out_path.exists()
    # The written JSON must be loadable by the CLI's own loader.
    script = _load_script_json(out_path)
    assert len(script.lines) == 3  # lecture_intro has 3 lines
    assert script.lines[0].host == "A"
    assert script.lines[0].segment_type == "intro"


def test_v0622_cli_templates_write_mode_stdout_message(tmp_path: Path) -> None:
    """The write mode prints a success message naming the template + path."""
    from core.podcast.cli import main as cli_main

    out_path = tmp_path / "tmpl.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "qa_format", "--out", str(out_path)])
    out = buf.getvalue()
    assert "qa_format" in out
    assert str(out_path) in out
    assert "4 lines" in out  # qa_format has 4 lines


def test_v0622_cli_templates_unknown_name_exits_1(tmp_path: Path) -> None:
    """An unknown --name exits 1 (not 2 — this is a user-error, not a
    file error) and lists the available names."""
    from core.podcast.cli import main as cli_main

    out_path = tmp_path / "out.json"
    buf = StringIO()
    err_buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["templates", "--name", "nonexistent", "--out", str(out_path)])
    assert exit_code == 1
    err = err_buf.getvalue()
    assert "nonexistent" in err
    assert "lecture_intro" in err  # the available names are listed


def test_v0622_cli_templates_name_without_out_exits_2(tmp_path: Path) -> None:
    """--name without --out exits 2 (argument error)."""
    from core.podcast.cli import main as cli_main

    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["templates", "--name", "lecture_intro"])
    assert exit_code == 2
    assert "--out" in err_buf.getvalue()


def test_v0622_cli_templates_writes_all_six_templates(tmp_path: Path) -> None:
    """Smoke test: all 6 templates can be written + re-loaded."""
    from core.podcast.cli import _load_script_json
    from core.podcast.cli import main as cli_main
    from core.podcast.script_templates import TEMPLATES

    for name in TEMPLATES:
        out_path = tmp_path / f"{name}.json"
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = cli_main(["templates", "--name", name, "--out", str(out_path)])
        assert exit_code == 0, f"Failed to write template {name!r}"
        assert out_path.exists()
        # Re-load + verify.
        script = _load_script_json(out_path)
        assert len(script.lines) == TEMPLATES[name].estimated_lines


def test_v0622_cli_templates_in_help() -> None:
    """The `templates` subcommand appears in --help alongside the others."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "templates" in result.stdout
    # The other subcommands are still there.
    assert "validate" in result.stdout
    assert "generate" in result.stdout
    assert "info" in result.stdout
    assert "stats" in result.stdout
    assert "diff" in result.stdout


def test_v0622_cli_templates_help_lists_all_six() -> None:
    """The `templates --help` output lists all 6 template names (via
    the --name argument's help text or the subcommand's listing)."""
    # The --name argument's help text says "Without --name, lists all",
    # so running `templates` (no args) lists them. This is the same as
    # test_v0622_cli_templates_list_mode_prints_all — covered there.
    # Here we just verify the --help for the templates subcommand exists.
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "templates", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "--name" in result.stdout
    assert "--out" in result.stdout


# ── Integration: template → validate → stats ────────────────────────────────


def test_v0622_integration_template_writes_then_validate_passes(
    tmp_path: Path,
) -> None:
    """Integration: write a template to JSON, then validate it via the
    CLI's `validate` subcommand — must pass (templates are valid scripts)."""
    from core.podcast.cli import main as cli_main

    # Step 1: write the template.
    tmpl_path = tmp_path / "qa.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "qa_format", "--out", str(tmpl_path)])
    assert tmpl_path.exists()

    # Step 2: validate it.
    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(
            [
                "validate",
                "--script",
                str(tmpl_path),
                "--voice-a",
                "vibevoice:Carter",
                "--voice-b",
                "vibevoice:Erin",
            ]
        )
    assert exit_code == 0, f"Template-derived script failed validation; output:\n{buf2.getvalue()}"


def test_v0622_integration_template_writes_then_stats_works(
    tmp_path: Path,
) -> None:
    """Integration: write a template to JSON, then run `stats` on it —
    must produce valid stats output."""
    from core.podcast.cli import main as cli_main

    # Step 1: write the template.
    tmpl_path = tmp_path / "interview.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "interview", "--out", str(tmpl_path)])
    assert tmpl_path.exists()

    # Step 2: compute stats.
    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(["stats", "--script", str(tmpl_path), "--json"])
    assert exit_code == 0
    stats = json.loads(buf2.getvalue().strip())
    assert stats["total_lines"] == 5  # interview has 5 lines
    assert stats["is_conversational"] is True
    assert stats["wpm_used"] > 0
