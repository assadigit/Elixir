"""V0.6.26 — the script-export + export-CLI batch pins.

This file pins the V0.6.26 additions:

Layer 1 — the SCRIPT EXPORT module (W-k1, NEW core/podcast/script_export.py):
  - ``export_to_srt(script, wpm)`` — SRT subtitle format with estimated
    timestamps (word count × WPM from V0.6.20's estimator).
  - ``export_to_html(script)`` — standalone HTML page with inline CSS.
  - ``export_to_markdown(script)`` — Markdown page (blockquote per line).
  - ``EXPORT_FORMATS`` registry + ``export(script, format)`` dispatcher.

Layer 2 — the CLI export subcommand (W-k2, core/podcast/cli.py):
  - ``export`` subcommand: lists all formats, or exports with
    ``--format <NAME> --script FILE [--out FILE] [--wpm N]``.

All tests are pure-Python (no PySide6 / no torch).
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── helpers ────────────────────────────────────────────────────────────────


def _make_script():
    from core.podcast.script_generator import ScriptLine, ScriptResult

    return ScriptResult(
        lines=[
            ScriptLine(
                host="A",
                text="Welcome to the show. Today we talk about testing.",
                source_ref="intro",
                segment_type="intro",
            ),
            ScriptLine(
                host="B",
                text="That's right. Testing is very important for software.",
                source_ref="content",
                segment_type="content",
            ),
            ScriptLine(
                host="A",
                text="Thanks for listening. See you next time.",
                source_ref="conclusion",
                segment_type="conclusion",
            ),
        ],
        title="Testing Podcast",
    )


def _write_script_json(path: Path) -> Path:
    """Write the test script to a JSON file."""

    script = _make_script()
    path.write_text(script.to_json(), encoding="utf-8")
    return path


# ── Layer 1a: SRT exporter ───────────────────────────────────────────────────


def test_v0626_export_to_srt_has_cue_indices() -> None:
    """The SRT output has 1-based cue indices (1, 2, 3, ...)."""
    from core.podcast.script_export import export_to_srt

    srt = export_to_srt(_make_script())
    lines = srt.strip().split("\n")
    # The first line of each cue is the index.
    indices = [lines[i] for i in range(0, len(lines), 4) if i < len(lines)]
    assert indices == ["1", "2", "3"]


def test_v0626_export_to_srt_has_timestamps() -> None:
    """The SRT output has start --> end timestamps in HH:MM:SS,mmm format."""
    from core.podcast.script_export import export_to_srt

    srt = export_to_srt(_make_script())
    # SRT timestamps use commas for the milliseconds separator.
    assert " --> " in srt
    assert "," in srt  # the milliseconds separator
    # Format: HH:MM:SS,mmm
    assert "00:00:00,000 --> " in srt  # the first cue starts at 0


def test_v0626_export_to_srt_includes_host_prefix() -> None:
    """Each SRT cue text includes the [Host A] / [Host B] prefix so the
    viewer knows who's speaking (SRT doesn't have a separate speaker field)."""
    from core.podcast.script_export import export_to_srt

    srt = export_to_srt(_make_script())
    assert "[Host A]" in srt
    assert "[Host B]" in srt


def test_v0626_export_to_srt_cues_are_sequential() -> None:
    """The SRT cues are sequential — each cue's start time = the previous
    cue's end time (no gaps, no overlaps)."""
    from core.podcast.script_export import export_to_srt

    srt = export_to_srt(_make_script())
    lines = srt.strip().split("\n")
    # Extract the end time of cue 1 and the start time of cue 2.
    cue1_end = lines[1].split(" --> ")[1]
    cue2_start = lines[5].split(" --> ")[0]
    assert cue1_end == cue2_start, (
        f"Cues are not sequential: cue 1 ends at {cue1_end}, cue 2 starts at {cue2_start}"
    )


def test_v0626_export_to_srt_empty_script_returns_empty_string() -> None:
    """An empty script produces an empty SRT string."""
    from core.podcast.script_export import export_to_srt
    from core.podcast.script_generator import ScriptResult

    srt = export_to_srt(ScriptResult(lines=[]))
    assert srt == ""


def test_v0626_export_to_srt_wpm_override() -> None:
    """The --wpm override changes the timestamps (slower WPM = longer duration)."""
    from core.podcast.script_export import export_to_srt

    fast = export_to_srt(_make_script(), wpm=300)
    slow = export_to_srt(_make_script(), wpm=100)
    # The slow SRT should have later end timestamps than the fast SRT.
    # SRT structure after .strip().split("\n"): each cue is 4 lines
    # (index, timestamp, text, blank) EXCEPT the last cue has no trailing
    # blank. So the last cue's timestamp line is lines[-2] (the second-to-
    # last line; the last line is the cue's text).
    fast_lines = fast.strip().split("\n")
    slow_lines = slow.strip().split("\n")
    fast_last_ts = fast_lines[-2]  # the last cue's timestamp line
    slow_last_ts = slow_lines[-2]
    fast_last_end = fast_last_ts.split(" --> ")[1]
    slow_last_end = slow_last_ts.split(" --> ")[1]
    assert slow_last_end > fast_last_end, (
        f"Slow WPM should produce later end time: slow={slow_last_end} fast={fast_last_end}"
    )


def test_v0626_format_srt_timestamp_format() -> None:
    """The _format_srt_timestamp function produces HH:MM:SS,mmm format."""
    from core.podcast.script_export import _format_srt_timestamp

    assert _format_srt_timestamp(0) == "00:00:00,000"
    assert _format_srt_timestamp(1.5) == "00:00:01,500"
    assert _format_srt_timestamp(73.5) == "00:01:13,500"
    assert _format_srt_timestamp(3661.5) == "01:01:01,500"
    assert _format_srt_timestamp(-5) == "00:00:00,000"  # negative clamped to 0


# ── Layer 1b: HTML exporter ─────────────────────────────────────────────────


def test_v0626_export_to_html_is_standalone() -> None:
    """The HTML output is a standalone HTML page (DOCTYPE, html, head, body)."""
    from core.podcast.script_export import export_to_html

    html = export_to_html(_make_script())
    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "<head>" in html
    assert "<body>" in html
    assert "</html>" in html


def test_v0626_export_to_html_has_title() -> None:
    """The HTML page has the script's title in <title> + <h1>."""
    from core.podcast.script_export import export_to_html

    html = export_to_html(_make_script())
    assert "<title>Testing Podcast</title>" in html
    assert "<h1>Testing Podcast</h1>" in html


def test_v0626_export_to_html_has_lines() -> None:
    """The HTML page has each line as a div with the speaker + text."""
    from core.podcast.script_export import export_to_html

    html = export_to_html(_make_script())
    assert "Host A:" in html
    assert "Host B:" in html
    assert "Welcome to the show" in html
    assert "Thanks for listening" in html


def test_v0626_export_to_html_escapes_special_chars() -> None:
    """The HTML exporter escapes & < > \" ' in the text (XSS prevention)."""
    from core.podcast.script_export import export_to_html
    from core.podcast.script_generator import ScriptLine, ScriptResult

    script = ScriptResult(
        lines=[
            ScriptLine(
                host="A",
                text='<script>alert("xss & stuff")</script>',
                source_ref="r",
                segment_type="intro",
            ),
        ],
    )
    html = export_to_html(script)
    assert "<script>alert" not in html  # the literal <script> tag must be escaped
    assert "&lt;script&gt;" in html  # escaped form
    assert "&amp;" in html  # the & must be escaped


def test_v0626_export_to_html_has_inline_css() -> None:
    """The HTML page has inline CSS (no external stylesheet dependency)."""
    from core.podcast.script_export import export_to_html

    html = export_to_html(_make_script())
    assert "<style>" in html
    assert ".host-a" in html
    assert ".host-b" in html


def test_v0626_export_to_html_empty_script() -> None:
    """An empty script produces an HTML page with the "(empty script)" message."""
    from core.podcast.script_export import export_to_html
    from core.podcast.script_generator import ScriptResult

    html = export_to_html(ScriptResult(lines=[]))
    assert "empty script" in html.lower()


def test_v0626_export_to_html_untitled_script() -> None:
    """A script with no title gets "Untitled Podcast" as the heading."""
    from core.podcast.script_export import export_to_html
    from core.podcast.script_generator import ScriptLine, ScriptResult

    script = ScriptResult(
        lines=[ScriptLine(host="A", text="hello", source_ref="r", segment_type="intro")],
    )
    html = export_to_html(script)
    assert "Untitled Podcast" in html


# ── Layer 1c: Markdown exporter ─────────────────────────────────────────────


def test_v0626_export_to_markdown_has_h1_title() -> None:
    """The Markdown output has an H1 (#) heading with the title."""
    from core.podcast.script_export import export_to_markdown

    md = export_to_markdown(_make_script())
    assert md.startswith("# Testing Podcast")


def test_v0626_export_to_markdown_has_blockquotes() -> None:
    """Each line is rendered as a blockquote (> **Host A:** text)."""
    from core.podcast.script_export import export_to_markdown

    md = export_to_markdown(_make_script())
    assert "> **Host A:**" in md
    assert "> **Host B:**" in md
    assert "Welcome to the show" in md


def test_v0626_export_to_markdown_empty_script() -> None:
    """An empty script produces a Markdown page with '(empty script)'."""
    from core.podcast.script_export import export_to_markdown
    from core.podcast.script_generator import ScriptResult

    md = export_to_markdown(ScriptResult(lines=[]))
    assert "empty script" in md.lower()


def test_v0626_export_to_markdown_untitled() -> None:
    """A script with no title gets '# Untitled Podcast'."""
    from core.podcast.script_export import export_to_markdown
    from core.podcast.script_generator import ScriptLine, ScriptResult

    script = ScriptResult(
        lines=[ScriptLine(host="A", text="hello", source_ref="r", segment_type="intro")],
    )
    md = export_to_markdown(script)
    assert "# Untitled Podcast" in md


# ── Layer 1d: the dispatcher + registry ─────────────────────────────────────


def test_v0626_export_dispatcher_srt() -> None:
    """The export() dispatcher routes 'srt' to export_to_srt."""
    from core.podcast.script_export import export, export_to_srt

    script = _make_script()
    assert export(script, "srt") == export_to_srt(script)


def test_v0626_export_dispatcher_html() -> None:
    """The export() dispatcher routes 'html' to export_to_html."""
    from core.podcast.script_export import export, export_to_html

    script = _make_script()
    assert export(script, "html") == export_to_html(script)


def test_v0626_export_dispatcher_markdown() -> None:
    """The export() dispatcher routes 'markdown' to export_to_markdown."""
    from core.podcast.script_export import export, export_to_markdown

    script = _make_script()
    assert export(script, "markdown") == export_to_markdown(script)


def test_v0626_export_dispatcher_unknown_format_raises() -> None:
    """An unknown format raises ValueError listing the available formats."""
    from core.podcast.script_export import export

    with pytest.raises(ValueError, match="Unknown export format"):
        export(_make_script(), "yaml")


def test_v0626_export_formats_registry_has_three_formats() -> None:
    """The EXPORT_FORMATS registry has exactly srt / html / markdown."""
    from core.podcast.script_export import EXPORT_FORMATS

    assert set(EXPORT_FORMATS.keys()) == {"srt", "html", "markdown"}


def test_v0626_list_formats_returns_all_three() -> None:
    """list_formats() returns all 3 formats with descriptions."""
    from core.podcast.script_export import list_formats

    formats = list_formats()
    names = [name for name, _desc in formats]
    assert set(names) == {"srt", "html", "markdown"}


def test_v0626_format_formats_for_display_has_header() -> None:
    """The display formatter has the header + all 3 format names."""
    from core.podcast.script_export import format_formats_for_display

    out = format_formats_for_display()
    assert "📤 Available Podcast Script Export Formats" in out
    assert "srt" in out
    assert "html" in out
    assert "markdown" in out


# ── Layer 2: the CLI export subcommand ──────────────────────────────────────


def test_v0626_cli_export_list_mode_prints_all_formats(tmp_path: Path) -> None:
    """`export --script FILE` without --format lists all available formats."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["export", "--script", str(script_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📤 Available Podcast Script Export Formats" in out
    for name in ("srt", "html", "markdown"):
        assert name in out


def test_v0626_cli_export_srt_to_stdout(tmp_path: Path) -> None:
    """`export --script FILE --format srt` prints the SRT to stdout."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["export", "--script", str(script_path), "--format", "srt"])
    assert exit_code == 0
    out = buf.getvalue()
    assert " --> " in out
    assert "[Host A]" in out


def test_v0626_cli_export_html_to_file(tmp_path: Path) -> None:
    """`export --script FILE --format html --out FILE` writes the HTML to a file."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    out_path = tmp_path / "output.html"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(
            [
                "export",
                "--script",
                str(script_path),
                "--format",
                "html",
                "--out",
                str(out_path),
            ]
        )
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Testing Podcast" in content


def test_v0626_cli_export_markdown_to_file(tmp_path: Path) -> None:
    """`export --script FILE --format markdown --out FILE` writes Markdown."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    out_path = tmp_path / "output.md"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(
            [
                "export",
                "--script",
                str(script_path),
                "--format",
                "markdown",
                "--out",
                str(out_path),
            ]
        )
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert content.startswith("# Testing Podcast")
    assert "> **Host A:**" in content


def test_v0626_cli_export_unknown_format_exits_1(tmp_path: Path) -> None:
    """An unknown --format exits 1 and lists the available formats."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(
            [
                "export",
                "--script",
                str(script_path),
                "--format",
                "yaml",
            ]
        )
    assert exit_code == 1
    assert "yaml" in err_buf.getvalue()
    assert "srt" in err_buf.getvalue()  # the available names are listed


def test_v0626_cli_export_missing_script_file_exits_2(tmp_path: Path) -> None:
    """A missing --script file exits 2."""
    from core.podcast.cli import main as cli_main

    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(
            [
                "export",
                "--script",
                str(tmp_path / "nope.json"),
                "--format",
                "srt",
            ]
        )
    assert exit_code == 2


def test_v0626_cli_export_bad_json_exits_2(tmp_path: Path) -> None:
    """A malformed script JSON exits 2."""
    from core.podcast.cli import main as cli_main

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not json", encoding="utf-8")
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["export", "--script", str(bad_path), "--format", "srt"])
    assert exit_code == 2


def test_v0626_cli_export_wpm_override(tmp_path: Path) -> None:
    """The --wpm flag overrides the auto-detected WPM for SRT timestamps."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    # Fast WPM (300) should produce shorter total duration than slow (100).
    buf_fast = StringIO()
    with contextlib.redirect_stdout(buf_fast):
        cli_main(["export", "--script", str(script_path), "--format", "srt", "--wpm", "300"])
    buf_slow = StringIO()
    with contextlib.redirect_stdout(buf_slow):
        cli_main(["export", "--script", str(script_path), "--format", "srt", "--wpm", "100"])
    # The last timestamp in the slow SRT should be later than in the fast SRT.
    # SRT structure: the last cue's timestamp line is lines[-2] (the last
    # line is the cue's text).
    fast_lines = buf_fast.getvalue().strip().split("\n")
    slow_lines = buf_slow.getvalue().strip().split("\n")
    fast_last_end = fast_lines[-2].split(" --> ")[1]
    slow_last_end = slow_lines[-2].split(" --> ")[1]
    assert slow_last_end > fast_last_end


def test_v0626_cli_export_in_help() -> None:
    """The `export` subcommand appears in --help alongside the others."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "export" in result.stdout
    # The other subcommands are still there.
    for sub in ("validate", "generate", "info", "stats", "diff", "templates", "schema"):
        assert sub in result.stdout


# ── Layer 3: integration (template -> export round-trip) ──────────────────


def test_v0626_integration_template_then_export_srt(tmp_path: Path) -> None:
    """Integration: write a V0.6.22 template to JSON, then export it to SRT
    via the CLI. The template's lines should appear in the SRT output."""
    from core.podcast.cli import main as cli_main

    # Step 1: write a template.
    tmpl_path = tmp_path / "qa.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "qa_format", "--out", str(tmpl_path)])
    assert tmpl_path.exists()

    # Step 2: export to SRT.
    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(["export", "--script", str(tmpl_path), "--format", "srt"])
    assert exit_code == 0
    srt = buf2.getvalue()
    assert " --> " in srt
    assert "[Host A]" in srt
    assert "[Host B]" in srt


def test_v0626_integration_template_then_export_html(tmp_path: Path) -> None:
    """Integration: write a V0.6.22 template, then export to HTML."""
    from core.podcast.cli import main as cli_main

    tmpl_path = tmp_path / "interview.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["templates", "--name", "interview", "--out", str(tmpl_path)])

    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(["export", "--script", str(tmpl_path), "--format", "html"])
    assert exit_code == 0
    html = buf2.getvalue()
    assert "<!DOCTYPE html>" in html
    assert "Interview Podcast" in html  # the template's title
