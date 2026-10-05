"""V0.6.21 — the script-diff + diff-CLI batch pins.

This file pins the V0.6.21 additions:

Layer 1 — the SCRIPT DIFF module (W-g1, NEW core/podcast/script_diff.py):
  - ``diff_scripts(before, after)`` — line-level diff using stdlib
    ``difflib.SequenceMatcher`` (Ratcliff-Obershel, the same algorithm
    git diff uses). Returns a ``ScriptDiff`` with .lines (list of
    ``LineDiff`` in line order) + .added_count / .deleted_count /
    .modified_count / .equal_count.
  - Word-level diffs WITHIN a modified line (so a 1-word tweak in a
    50-word line shows just that 1 word, not the whole line as a
    delete+add pair).
  - ``summarize_diff(diff)`` — one-line summary (e.g., "3 added, 1
    deleted, 2 modified").
  - ``format_diff_for_display(diff, log, context)`` — git-diff-style
    multi-line formatter (green +, red -, ~ for modified, space for
    context; ``context`` controls how many unchanged lines to show
    around each change).

Layer 2 — the CLI diff subcommand (W-g2, core/podcast/cli.py):
  - ``diff`` subcommand: prints the diff to stdout.
  - ``--context N`` flag: controls unchanged-line context (default 2,
    git's default; 0 = changes only).
  - ``--summary-only`` flag: prints just the one-line summary.
  - Exits 0 on success (even if there are changes), 2 on file/parse
    error (same contract as info/stats).

All tests are pure-Python (no PySide6 / no torch / no soundfile).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared helpers ──────────────────────────────────────────────────────────


def _make_line(host: str = "A", text: str = "hello", segment_type: str = "content"):
    from core.podcast.script_generator import ScriptLine

    return ScriptLine(host=host, text=text, source_ref="ref", segment_type=segment_type)


def _make_script(lines=None, title: str = "test"):
    from core.podcast.script_generator import ScriptResult

    if lines is None:
        lines = [
            _make_line("A", "intro line", "intro"),
            _make_line("B", "body line", "content"),
            _make_line("A", "conclusion line", "conclusion"),
        ]
    return ScriptResult(lines=lines, title=title)


def _write_script_json(
    path: Path,
    lines: list[dict] | None = None,
    title: str = "test",
) -> Path:
    if lines is None:
        lines = [
            {"host": "A", "text": "intro line", "source_ref": "ref", "segment_type": "intro"},
            {"host": "B", "text": "body line", "source_ref": "ref", "segment_type": "content"},
            {
                "host": "A",
                "text": "conclusion line",
                "source_ref": "ref",
                "segment_type": "conclusion",
            },
        ]
    data = {
        "lines": lines,
        "title": title,
        "bullets_input": [],
        "bullets_covered": [],
        "bullets_missing": [],
        "coverage_pct": 100.0,
        "retries": 0,
        "forced_segments": 0,
        "error": None,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── Layer 1: the script diff module ─────────────────────────────────────────


def test_v0621_diff_identical_scripts_is_clean() -> None:
    """Two identical scripts produce a clean diff (zero changes)."""
    from core.podcast.script_diff import diff_scripts

    script = _make_script()
    diff = diff_scripts(script, _make_script())
    assert diff.is_clean is True
    assert diff.total_changes == 0
    assert diff.added_count == 0
    assert diff.deleted_count == 0
    assert diff.modified_count == 0
    assert diff.equal_count == 3


def test_v0621_diff_added_lines() -> None:
    """Lines added to the `after` script are reported as OP_INSERT."""
    from core.podcast.script_diff import OP_INSERT, diff_scripts

    before = _make_script(
        lines=[_make_line("A", "line 1", "intro"), _make_line("A", "line 2", "content")]
    )
    after = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "new line", "content"),  # added
            _make_line("A", "line 2", "content"),
        ]
    )
    diff = diff_scripts(before, after)
    assert diff.added_count == 1
    assert diff.deleted_count == 0
    assert diff.modified_count == 0
    inserts = [ld for ld in diff.lines if ld.op == OP_INSERT]
    assert len(inserts) == 1
    assert inserts[0].after.text == "new line"


def test_v0621_diff_deleted_lines() -> None:
    """Lines removed from the `after` script are reported as OP_DELETE."""
    from core.podcast.script_diff import OP_DELETE, diff_scripts

    before = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "to be deleted", "content"),
            _make_line("A", "line 2", "content"),
        ]
    )
    after = _make_script(
        lines=[_make_line("A", "line 1", "intro"), _make_line("A", "line 2", "content")]
    )
    diff = diff_scripts(before, after)
    assert diff.deleted_count == 1
    assert diff.added_count == 0
    deletes = [ld for ld in diff.lines if ld.op == OP_DELETE]
    assert len(deletes) == 1
    assert deletes[0].before.text == "to be deleted"


def test_v0621_diff_modified_line_text() -> None:
    """A line whose text changed (same host + segment) is OP_REPLACE
    with word-level diffs populated."""
    from core.podcast.script_diff import OP_REPLACE, diff_scripts

    before = _make_script(lines=[_make_line("A", "the quick brown fox", "intro")])
    after = _make_script(
        lines=[_make_line("A", "the slow brown fox", "intro")]  # quick -> slow
    )
    diff = diff_scripts(before, after)
    assert diff.modified_count == 1
    replaces = [ld for ld in diff.lines if ld.op == OP_REPLACE]
    assert len(replaces) == 1
    # Word-level diffs should be populated.
    assert len(replaces[0].word_diffs) > 0
    # The word "quick" should be in a DELETE word-diff, "slow" in an INSERT.
    deletes = [wd for wd in replaces[0].word_diffs if wd.op == "delete"]
    inserts = [wd for wd in replaces[0].word_diffs if wd.op == "insert"]
    assert any("quick" in wd.before for wd in deletes)
    assert any("slow" in wd.after for wd in inserts)


def test_v0621_diff_modified_line_host_only() -> None:
    """A line whose host changed (same text + segment) is OP_REPLACE
    but with NO word-level diffs (the text is identical)."""
    from core.podcast.script_diff import OP_REPLACE, diff_scripts

    before = _make_script(lines=[_make_line("A", "same text", "intro")])
    after = _make_script(lines=[_make_line("B", "same text", "intro")])  # host change
    diff = diff_scripts(before, after)
    assert diff.modified_count == 1
    replaces = [ld for ld in diff.lines if ld.op == OP_REPLACE]
    assert len(replaces) == 1
    # The text is identical, so word_diffs should all be OP_EQUAL (no
    # delete/insert word-level ops).
    assert all(wd.op == "equal" for wd in replaces[0].word_diffs)


def test_v0621_diff_modified_line_segment_only() -> None:
    """A line whose segment_type changed (same host + text) is OP_REPLACE
    but with NO word-level diffs."""
    from core.podcast.script_diff import OP_REPLACE, diff_scripts

    before = _make_script(lines=[_make_line("A", "same text", "intro")])
    after = _make_script(lines=[_make_line("A", "same text", "content")])  # segment change
    diff = diff_scripts(before, after)
    assert diff.modified_count == 1
    replaces = [ld for ld in diff.lines if ld.op == OP_REPLACE]
    assert len(replaces) == 1
    assert all(wd.op == "equal" for wd in replaces[0].word_diffs)


def test_v0621_diff_source_ref_change_is_ignored() -> None:
    """A source_ref change alone is NOT a line modification — source_ref
    is metadata, not content. The diff treats the lines as equal."""
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


def test_v0621_diff_mixed_add_delete_modify() -> None:
    """A script with adds + deletes + modifies is all three in the diff."""
    from core.podcast.script_diff import diff_scripts

    before = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("B", "to delete", "content"),
            _make_line("A", "to modify", "content"),
            _make_line("A", "line 4", "conclusion"),
        ]
    )
    after = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "to modify CHANGED", "content"),  # modified
            _make_line("A", "line 4", "conclusion"),
            _make_line("B", "new line", "content"),  # added
        ]
    )
    diff = diff_scripts(before, after)
    assert diff.added_count == 1
    assert diff.deleted_count == 1
    assert diff.modified_count == 1
    assert diff.equal_count == 2  # line 1 + line 4


def test_v0621_diff_empty_scripts() -> None:
    """Two empty scripts produce a clean diff."""
    from core.podcast.script_diff import diff_scripts
    from core.podcast.script_generator import ScriptResult

    diff = diff_scripts(ScriptResult(lines=[]), ScriptResult(lines=[]))
    assert diff.is_clean is True
    assert diff.equal_count == 0


def test_v0621_diff_before_empty_after_populated() -> None:
    """Before empty + after populated = all lines are INSERTs."""
    from core.podcast.script_diff import OP_INSERT, diff_scripts
    from core.podcast.script_generator import ScriptResult

    after = _make_script(lines=[_make_line("A", "x", "intro"), _make_line("B", "y", "content")])
    diff = diff_scripts(ScriptResult(lines=[]), after)
    assert diff.added_count == 2
    assert all(ld.op == OP_INSERT for ld in diff.lines)


def test_v0621_diff_before_populated_after_empty() -> None:
    """Before populated + after empty = all lines are DELETEs."""
    from core.podcast.script_diff import OP_DELETE, diff_scripts
    from core.podcast.script_generator import ScriptResult

    before = _make_script(lines=[_make_line("A", "x", "intro")])
    diff = diff_scripts(before, ScriptResult(lines=[]))
    assert diff.deleted_count == 1
    assert all(ld.op == OP_DELETE for ld in diff.lines)


def test_v0621_diff_titles_echoed() -> None:
    """The before_title + after_title are echoed from the scripts."""
    from core.podcast.script_diff import diff_scripts

    before = _make_script(title="Generated Script")
    after = _make_script(title="Edited Script")
    diff = diff_scripts(before, after)
    assert diff.before_title == "Generated Script"
    assert diff.after_title == "Edited Script"


def test_v0621_diff_line_indices_are_1_based() -> None:
    """The before_index / after_index are 1-based (human-friendly)."""
    from core.podcast.script_diff import OP_EQUAL, diff_scripts

    before = _make_script(
        lines=[_make_line("A", "line 1", "intro"), _make_line("A", "line 2", "content")]
    )
    diff = diff_scripts(before, _make_script(lines=before.lines))
    equals = [ld for ld in diff.lines if ld.op == OP_EQUAL]
    assert equals[0].before_index == 1
    assert equals[1].before_index == 2
    assert equals[0].after_index == 1
    assert equals[1].after_index == 2


# ── summarize_diff + format_diff_for_display ─────────────────────────────────


def test_v0621_summarize_diff_clean() -> None:
    """A clean diff produces the canonical 'No changes' summary."""
    from core.podcast.script_diff import diff_scripts, summarize_diff

    script = _make_script()
    diff = diff_scripts(script, _make_script())
    summary = summarize_diff(diff)
    assert "✅" in summary
    assert "No changes" in summary


def test_v0621_summarize_diff_with_changes() -> None:
    """A diff with changes produces a summary naming each change type."""
    from core.podcast.script_diff import diff_scripts, summarize_diff

    before = _make_script(lines=[_make_line("A", "x", "intro"), _make_line("A", "y", "content")])
    after = _make_script(
        lines=[
            _make_line("A", "x", "intro"),
            _make_line("A", "y CHANGED", "content"),  # modified
            _make_line("B", "new", "content"),  # added
        ]
    )
    diff = diff_scripts(before, after)
    summary = summarize_diff(diff)
    assert "1 added" in summary
    assert "1 modified" in summary
    assert "2 total changes" in summary


def test_v0621_format_diff_clean_returns_summary() -> None:
    """A clean diff's formatted output is just the summary line."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    script = _make_script()
    diff = diff_scripts(script, _make_script())
    out = format_diff_for_display(diff)
    assert "No changes" in out
    # No git-diff-style header for a clean diff.
    assert "Script Diff" not in out


def test_v0621_format_diff_with_changes_has_header_and_summary() -> None:
    """A diff with changes has the header + the changed lines."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    before = _make_script(lines=[_make_line("A", "x", "intro"), _make_line("A", "y", "content")])
    after = _make_script(
        lines=[_make_line("A", "x", "intro"), _make_line("A", "y changed", "content")]
    )
    diff = diff_scripts(before, after)
    out = format_diff_for_display(diff)
    assert "📝 Script Diff" in out
    assert "Summary:" in out
    # The modified line should be in the output with the ~ prefix.
    assert "~" in out


def test_v0621_format_diff_context_zero_shows_only_changes() -> None:
    """--context 0 shows ONLY the changed lines (no equal lines, no ...)."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    before = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "line 2", "content"),
            _make_line("A", "line 3", "content"),
            _make_line("A", "line 4", "content"),
        ]
    )
    after = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "line 2 CHANGED", "content"),  # modified
            _make_line("A", "line 3", "content"),
            _make_line("A", "line 4", "content"),
        ]
    )
    diff = diff_scripts(before, after)
    out = format_diff_for_display(diff, context=0)
    # The modified line 2 should appear (with word-diff markers breaking
    # up the text — 'line 2 [+CHANGED+]').
    assert "line 2" in out
    assert "CHANGED" in out
    # The UNCHANGED lines 1, 3, 4 should NOT appear as context lines.
    # (They might appear in the header's Before:/After: titles if the
    # title contains them, but not as diff lines with the '  N  ' prefix.)
    # Check that no line starts with '  1  ' or '  3  ' or '  4  ' (the
    # equal-line format).
    for line in out.split("\n"):
        # Equal lines have the format '  N  [host] text'.
        if line.startswith("  1  ") or line.startswith("  3  ") or line.startswith("  4  "):
            pytest.fail(f"unchanged line appeared in context=0 output: {line!r}")
    # No '...' context separators.
    assert "..." not in out


def test_v0621_format_diff_context_two_shows_surrounding_lines() -> None:
    """--context 2 (default) shows 2 unchanged lines around each change."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    before = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "line 2", "content"),
            _make_line("A", "line 3 to modify", "content"),
            _make_line("A", "line 4", "content"),
            _make_line("A", "line 5", "content"),
        ]
    )
    after = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "line 2", "content"),
            _make_line("A", "line 3 CHANGED", "content"),  # modified at index 2
            _make_line("A", "line 4", "content"),
            _make_line("A", "line 5", "content"),
        ]
    )
    diff = diff_scripts(before, after)
    out = format_diff_for_display(diff, context=2)
    # The changed line + 2 on each side = lines 1, 2, 3, 4, 5 — all of them.
    # (The change is in the middle so context reaches both ends.)
    # The word-diff markers break up 'line 3 CHANGED' into 'line 3 [-to modify-] [+CHANGED+]'
    # so we check for the component parts.
    assert "line 1" in out
    assert "line 2" in out
    assert "line 3" in out
    assert "CHANGED" in out
    assert "line 4" in out
    assert "line 5" in out


def test_v0621_format_diff_context_with_skips() -> None:
    """When the changes are far apart, the formatter skips the middle
    with a '...' separator (git-diff style)."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    # 10 lines, changes at index 1 and 8, context=1 → shows 0-1, skips 2-6,
    # shows 7-9 (with a '...' in the middle).
    before_lines = [_make_line("A", f"line {i}", "content") for i in range(10)]
    after_lines = list(before_lines)
    after_lines[1] = _make_line("A", "line 1 CHANGED", "content")
    after_lines[8] = _make_line("A", "line 8 CHANGED", "content")
    before = _make_script(lines=before_lines)
    after = _make_script(lines=after_lines)
    diff = diff_scripts(before, after)
    out = format_diff_for_display(diff, context=1)
    # The "..." skip separator should be present (the middle is skipped).
    assert "..." in out


def test_v0621_format_diff_log_callback_called() -> None:
    """The log callback is called for each output line."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    before = _make_script(lines=[_make_line("A", "x", "intro")])
    after = _make_script(lines=[_make_line("A", "x changed", "intro")])
    diff = diff_scripts(before, after)
    logs: list[tuple[str, str]] = []
    format_diff_for_display(diff, log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0
    # Modified lines should be logged at WARNING level; equals at INFO.
    levels = {level for _, level in logs}
    assert "WARNING" in levels or "INFO" in levels


def test_v0621_format_diff_word_level_inline() -> None:
    """A modified line's word-level diff is shown inline with [-old-] and
    [+new+] markers."""
    from core.podcast.script_diff import diff_scripts, format_diff_for_display

    before = _make_script(lines=[_make_line("A", "the quick brown fox", "intro")])
    after = _make_script(lines=[_make_line("A", "the slow brown fox", "intro")])
    diff = diff_scripts(before, after)
    out = format_diff_for_display(diff, context=0)
    # The word "quick" should be in a [-...-] delete marker, "slow" in a
    # [+...+] insert marker.
    assert "[-quick-]" in out
    assert "[+slow+]" in out


# ── Layer 2: the CLI diff subcommand ────────────────────────────────────────


def test_v0621_cli_diff_subcommand_prints_diff(tmp_path: Path) -> None:
    """The `diff` subcommand prints the diff to stdout; exits 0 on success."""
    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(
        tmp_path / "a.json",
        lines=[{"host": "A", "text": "hello world", "source_ref": "r", "segment_type": "intro"}],
        title="A",
    )
    path_b = _write_script_json(
        tmp_path / "b.json",
        lines=[{"host": "A", "text": "hello there", "source_ref": "r", "segment_type": "intro"}],
        title="B",
    )
    exit_code = cli_main(["diff", "--script-a", str(path_a), "--script-b", str(path_b)])
    assert exit_code == 0


def test_v0621_cli_diff_clean_scripts_exit_zero(tmp_path: Path) -> None:
    """Two identical scripts produce exit 0 (no changes is not an error)."""
    from core.podcast.cli import main as cli_main

    path = _write_script_json(tmp_path / "a.json", title="same")
    path_b = _write_script_json(tmp_path / "b.json", title="same")
    # Both scripts have the same content.
    exit_code = cli_main(["diff", "--script-a", str(path), "--script-b", str(path_b)])
    assert exit_code == 0


def test_v0621_cli_diff_missing_file_a_exits_2(tmp_path: Path) -> None:
    """Missing --script-a file exits 2."""
    from core.podcast.cli import main as cli_main

    path_b = _write_script_json(tmp_path / "b.json")
    exit_code = cli_main(
        ["diff", "--script-a", str(tmp_path / "nope.json"), "--script-b", str(path_b)]
    )
    assert exit_code == 2


def test_v0621_cli_diff_missing_file_b_exits_2(tmp_path: Path) -> None:
    """Missing --script-b file exits 2."""
    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(tmp_path / "a.json")
    exit_code = cli_main(
        ["diff", "--script-a", str(path_a), "--script-b", str(tmp_path / "nope.json")]
    )
    assert exit_code == 2


def test_v0621_cli_diff_bad_json_exits_2(tmp_path: Path) -> None:
    """Malformed JSON exits 2."""
    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(tmp_path / "a.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    exit_code = cli_main(["diff", "--script-a", str(path_a), "--script-b", str(bad)])
    assert exit_code == 2


def test_v0621_cli_diff_summary_only_flag(tmp_path: Path) -> None:
    """--summary-only prints just the one-line summary, not the full diff."""
    import contextlib
    from io import StringIO

    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(
        tmp_path / "a.json",
        lines=[{"host": "A", "text": "hello", "source_ref": "r", "segment_type": "intro"}],
        title="A",
    )
    path_b = _write_script_json(
        tmp_path / "b.json",
        lines=[{"host": "A", "text": "goodbye", "source_ref": "r", "segment_type": "intro"}],
        title="B",
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["diff", "--script-a", str(path_a), "--script-b", str(path_b), "--summary-only"])
    out = buf.getvalue().strip()
    # The summary-only output is ONE line with the summary.
    assert "modified" in out
    assert "📝 Script Diff" not in out  # no header in summary mode


def test_v0621_cli_diff_context_zero_flag(tmp_path: Path) -> None:
    """--context 0 prints only the changed lines (no surrounding context)."""
    import contextlib
    from io import StringIO

    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(
        tmp_path / "a.json",
        lines=[
            {"host": "A", "text": "line 1", "source_ref": "r", "segment_type": "intro"},
            {"host": "A", "text": "line 2", "source_ref": "r", "segment_type": "content"},
            {"host": "A", "text": "line 3", "source_ref": "r", "segment_type": "conclusion"},
        ],
        title="A",
    )
    path_b = _write_script_json(
        tmp_path / "b.json",
        lines=[
            {"host": "A", "text": "line 1", "source_ref": "r", "segment_type": "intro"},
            {"host": "A", "text": "line 2 CHANGED", "source_ref": "r", "segment_type": "content"},
            {"host": "A", "text": "line 3", "source_ref": "r", "segment_type": "conclusion"},
        ],
        title="B",
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["diff", "--script-a", str(path_a), "--script-b", str(path_b), "--context", "0"])
    out = buf.getvalue()
    # With context=0, only the changed line (line 2) should appear, not
    # the unchanged lines 1 and 3.
    # The word-diff markers break up 'line 2 CHANGED' into 'line 2 [+CHANGED+]'
    # so we check for the component parts.
    assert "line 2" in out
    assert "CHANGED" in out
    # The unchanged lines 1 and 3 should NOT appear as context lines.
    for line in out.split("\n"):
        if line.startswith("  1  ") or line.startswith("  3  "):
            pytest.fail(f"unchanged line appeared in context=0 output: {line!r}")


def test_v0621_cli_diff_in_help() -> None:
    """The `diff` subcommand appears in --help alongside the others."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "diff" in result.stdout
    # The other subcommands are still there.
    assert "validate" in result.stdout
    assert "generate" in result.stdout
    assert "info" in result.stdout
    assert "stats" in result.stdout


def test_v0621_cli_diff_word_level_markers_in_output(tmp_path: Path) -> None:
    """The diff output shows word-level [-old-] / [+new+] markers for
    modified lines (the V0.6.21 word-diff contract)."""
    import contextlib
    from io import StringIO

    from core.podcast.cli import main as cli_main

    path_a = _write_script_json(
        tmp_path / "a.json",
        lines=[
            {"host": "A", "text": "the quick brown fox", "source_ref": "r", "segment_type": "intro"}
        ],
        title="A",
    )
    path_b = _write_script_json(
        tmp_path / "b.json",
        lines=[
            {"host": "A", "text": "the slow brown fox", "source_ref": "r", "segment_type": "intro"}
        ],
        title="B",
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["diff", "--script-a", str(path_a), "--script-b", str(path_b), "--context", "0"])
    out = buf.getvalue()
    assert "[-quick-]" in out
    assert "[+slow+]" in out
