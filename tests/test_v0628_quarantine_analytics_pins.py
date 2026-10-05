"""V0.6.28 — the quarantine analytics + summarisation CLI batch pins.

This file pins the V0.6.28 additions — the SECOND round working on a
DIFFERENT module (summarisation) than the podcast module:

Layer 1 — the QUARANTINE ANALYTICS module (W-m1, NEW
core/summarisation/quarantine_analytics.py):
  - ``compute_quarantine_stats(log)`` — returns a ``QuarantineStats``
    with total/dropped/conservative/recovered counts, recovery_rate,
    overlap distribution (min/max/mean/median), per-stage + per-chapter
    breakdowns.
  - ``format_quarantine_stats_for_display(stats, log)`` — multi-line
    formatter.
  - ``export_to_csv(log)`` — CSV with all 10 fields + header row.
  - ``export_to_json(log)`` — wraps the existing ``serialize()``.
  - ``export_to_markdown(log)`` — human-readable report with stats + a
    table of dropped bullets.
  - ``QUARANTINE_EXPORT_FORMATS`` registry + ``export_quarantine()``
    dispatcher.

Layer 2 — the summarisation CLI (W-m2, NEW core/summarisation/cli.py):
  - ``stats --drops <FILE>`` — prints quarantine statistics.
  - ``export --drops <FILE> [--format csv|json|markdown] [--out FILE]``
    — lists all formats, or exports to stdout/file.
  - Exits 0 on success, 1 on unknown format, 2 on file error.

The quarantine module is pure stdlib but core.summarisation.__init__
imports Summarizer which pulls in tiktoken (not installed). The tests
load the modules via importlib.util (the same pattern test_quarantine.py
uses) to bypass the import chain.

All tests are pure-Python (no PySide6 / no torch / no tiktoken).
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load quarantine.py + quarantine_analytics.py + cli.py via importlib to
# bypass core.summarisation.__init__ (which pulls in tiktoken).
# The load sequence must register each module in sys.modules BEFORE
# exec_module runs, so that @dataclass decorators can find the module's
# namespace via sys.modules[cls.__module__].__dict__.
_quarantine_spec = importlib.util.spec_from_file_location(
    "core.summarisation.quarantine",
    _project_root / "core" / "summarisation" / "quarantine.py",
)
_quarantine_mod = importlib.util.module_from_spec(_quarantine_spec)
sys.modules["core.summarisation.quarantine"] = _quarantine_mod  # register BEFORE exec
_quarantine_spec.loader.exec_module(_quarantine_mod)

_analytics_spec = importlib.util.spec_from_file_location(
    "core.summarisation.quarantine_analytics",
    _project_root / "core" / "summarisation" / "quarantine_analytics.py",
)
_analytics = importlib.util.module_from_spec(_analytics_spec)
sys.modules["core.summarisation.quarantine_analytics"] = _analytics  # register BEFORE exec
_analytics_spec.loader.exec_module(_analytics)

_cli_spec = importlib.util.spec_from_file_location(
    "core.summarisation.cli",
    _project_root / "core" / "summarisation" / "cli.py",
)
_cli = importlib.util.module_from_spec(_cli_spec)
sys.modules["core.summarisation.cli"] = _cli  # register BEFORE exec
# Set the __file__ for the CLI module so its deferred import path works.
_cli.__file__ = str(_project_root / "core" / "summarisation" / "cli.py")
_cli_spec.loader.exec_module(_cli)

# Convenience aliases.
QuarantineEntry = _quarantine_mod.QuarantineEntry
QuarantineLog = _quarantine_mod.QuarantineLog


# ── helpers ────────────────────────────────────────────────────────────────


def _make_log_with_entries():
    """Build a QuarantineLog (in-memory, no disk) with a mix of entries."""
    log = QuarantineLog(output_dir=None)
    log.add("bullet 1", stage="F4_source_overlap", source_overlap=0.45, actually_dropped=True)
    log.add("bullet 2", stage="F4_source_overlap", source_overlap=0.18, actually_dropped=True)
    log.add("bullet 3", stage="B3_dedup", source_overlap=0.05, actually_dropped=True)
    log.add("bullet 4", stage="B3_dedup", source_overlap=0.92, actually_dropped=True)
    log.add(
        "conservative 1", stage="F4_source_overlap", source_overlap=0.30, actually_dropped=False
    )
    return log


def _make_log_with_recovery():
    """Build a QuarantineLog where some bullets were recovered."""
    log = QuarantineLog(output_dir=None)
    log.add("recovered 1", stage="F4", source_overlap=0.50, actually_dropped=True)
    log.add("recovered 2", stage="F4", source_overlap=0.45, actually_dropped=True)
    log.add("not recovered", stage="F4", source_overlap=0.10, actually_dropped=True)
    # Mark the first two as recovered.
    log.mark_recovered("recovered 1")
    log.mark_recovered("recovered 2")
    return log


def _write_drops_jsonl(path: Path, entries) -> Path:
    """Write a list of QuarantineEntry objects to a drops.jsonl file."""
    lines = [json.dumps(e.to_dict(), ensure_ascii=False) for e in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── Layer 1a: compute_quarantine_stats ──────────────────────────────────────


def test_v0628_compute_stats_empty_log() -> None:
    """An empty log produces zero-stats."""
    log = QuarantineLog(output_dir=None)
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.is_empty is True
    assert stats.total_entries == 0
    assert stats.dropped_count == 0
    assert stats.recovery_rate == 0.0


def test_v0628_compute_stats_total_entries() -> None:
    """The total_entries count matches the log's entry count."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.total_entries == 5


def test_v0628_compute_stats_dropped_vs_conservative() -> None:
    """The dropped/conservative counts are correct (4 dropped, 1 conservative)."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.dropped_count == 4
    assert stats.conservative_count == 1


def test_v0628_compute_stats_recovered_count() -> None:
    """The recovered_count is correct (2 recovered in the recovery log)."""
    log = _make_log_with_recovery()
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.recovered_count == 2
    assert stats.dropped_count == 3  # all 3 were dropped


def test_v0628_compute_stats_recovery_rate() -> None:
    """The recovery_rate is (recovered / dropped) = (2/3) ≈ 0.667."""
    log = _make_log_with_recovery()
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.recovery_rate == pytest.approx(2 / 3, abs=0.01)


def test_v0628_compute_stats_recovery_rate_zero_when_no_drops() -> None:
    """The recovery_rate is 0.0 when there are no drops (no division by zero)."""
    log = QuarantineLog(output_dir=None)
    log.add("conservative only", stage="F4", source_overlap=0.30, actually_dropped=False)
    stats = _analytics.compute_quarantine_stats(log)
    assert stats.recovery_rate == 0.0


def test_v0628_compute_stats_overlap_distribution() -> None:
    """The overlap distribution (min/max/mean/median) is computed correctly."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    # The overlaps > 0 are: 0.45, 0.18, 0.05, 0.92, 0.30
    assert stats.overlap_min == pytest.approx(0.05, abs=0.001)
    assert stats.overlap_max == pytest.approx(0.92, abs=0.001)
    assert stats.overlap_mean == pytest.approx((0.45 + 0.18 + 0.05 + 0.92 + 0.30) / 5, abs=0.01)
    # median of [0.05, 0.18, 0.30, 0.45, 0.92] = 0.30
    assert stats.overlap_median == pytest.approx(0.30, abs=0.01)


def test_v0628_compute_stats_stage_breakdown() -> None:
    """The stage_breakdown has one entry per unique stage, with correct counts."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    stage_map = {sb.stage: sb for sb in stats.stage_breakdown}
    assert "F4_source_overlap" in stage_map
    assert "B3_dedup" in stage_map
    # F4_source_overlap: 3 total (2 dropped + 1 conservative), 0 recovered
    f4 = stage_map["F4_source_overlap"]
    assert f4.total == 3
    assert f4.dropped == 2
    assert f4.conservative == 1
    assert f4.recovered == 0
    # B3_dedup: 2 total (2 dropped, 0 conservative)
    b3 = stage_map["B3_dedup"]
    assert b3.total == 2
    assert b3.dropped == 2
    assert b3.conservative == 0


def test_v0628_compute_stats_stage_breakdown_sorted_by_total_desc() -> None:
    """The stage_breakdown is sorted by total (desc) then stage name (asc)."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    # F4_source_overlap has 3, B3_dedup has 2 — F4 should be first.
    assert stats.stage_breakdown[0].stage == "F4_source_overlap"
    assert stats.stage_breakdown[1].stage == "B3_dedup"


def test_v0628_compute_stats_chapter_breakdown() -> None:
    """The chapter_breakdown groups by chapter (empty → '(unknown)')."""
    log = QuarantineLog(output_dir=None)
    log.add("b1", stage="F4", chapter="Chapter 1")
    log.add("b2", stage="F4", chapter="Chapter 1")
    log.add("b3", stage="F4", chapter="Chapter 2")
    log.add("b4", stage="F4", chapter="")  # no chapter → (unknown)
    stats = _analytics.compute_quarantine_stats(log)
    chapter_map = {cb.chapter: cb for cb in stats.chapter_breakdown}
    assert chapter_map["Chapter 1"].total == 2
    assert chapter_map["Chapter 2"].total == 1
    assert chapter_map["(unknown)"].total == 1


# ── Layer 1b: format_quarantine_stats_for_display ───────────────────────────


def test_v0628_format_stats_empty_log_message() -> None:
    """An empty log's display is the '✅ Empty quarantine log' message."""
    log = QuarantineLog(output_dir=None)
    stats = _analytics.compute_quarantine_stats(log)
    out = _analytics.format_quarantine_stats_for_display(stats)
    assert "✅" in out
    assert "Empty quarantine log" in out


def test_v0628_format_stats_has_all_sections() -> None:
    """A populated log's display has all the expected sections."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    out = _analytics.format_quarantine_stats_for_display(stats)
    assert "📊 Quarantine Log Statistics" in out
    assert "Total entries:" in out
    assert "Dropped:" in out
    assert "Conservative:" in out
    assert "Recovered:" in out
    assert "Source overlap distribution:" in out
    assert "Per-stage breakdown:" in out
    assert "Per-chapter breakdown:" in out


def test_v0628_format_stats_log_callback() -> None:
    """The log callback is called for each output line."""
    log = _make_log_with_entries()
    stats = _analytics.compute_quarantine_stats(log)
    logs: list[tuple[str, str]] = []
    _analytics.format_quarantine_stats_for_display(stats, log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0


# ── Layer 1c: CSV exporter ──────────────────────────────────────────────────


def test_v0628_export_to_csv_has_header_row() -> None:
    """The CSV output has a header row with all 10 field names."""
    log = _make_log_with_entries()
    csv_str = _analytics.export_to_csv(log)
    first_line = csv_str.strip().split("\n")[0]
    assert "bullet" in first_line
    assert "stage" in first_line
    assert "source_overlap" in first_line
    assert "actually_dropped" in first_line
    assert "recovered" in first_line


def test_v0628_export_to_csv_has_all_entries() -> None:
    """The CSV output has a header + one row per entry (5+1=6 lines)."""
    log = _make_log_with_entries()
    csv_str = _analytics.export_to_csv(log)
    lines = csv_str.strip().split("\n")
    assert len(lines) == 6  # header + 5 entries


def test_v0628_export_to_csv_empty_log_has_header_only() -> None:
    """An empty log produces a CSV with just the header row."""
    log = QuarantineLog(output_dir=None)
    csv_str = _analytics.export_to_csv(log)
    lines = csv_str.strip().split("\n")
    assert len(lines) == 1  # just the header


def test_v0628_export_to_csv_handles_commas_in_bullet() -> None:
    """A bullet with a comma is properly quoted in the CSV output."""
    log = QuarantineLog(output_dir=None)
    log.add("hello, world", stage="F4")
    csv_str = _analytics.export_to_csv(log)
    assert '"hello, world"' in csv_str


# ── Layer 1d: JSON exporter ──────────────────────────────────────────────────


def test_v0628_export_to_json_is_valid_json() -> None:
    """The JSON output is valid JSON (parseable)."""
    log = _make_log_with_entries()
    json_str = _analytics.export_to_json(log)
    data = json.loads(json_str)  # must not raise
    assert isinstance(data, list)
    assert len(data) == 5


def test_v0628_export_to_json_matches_serialize() -> None:
    """The JSON exporter wraps serialize() — the parsed JSON matches."""
    log = _make_log_with_entries()
    json_str = _analytics.export_to_json(log)
    parsed = json.loads(json_str)
    assert parsed == log.serialize()


def test_v0628_export_to_json_empty_log() -> None:
    """An empty log produces a JSON empty array '[]'."""
    log = QuarantineLog(output_dir=None)
    json_str = _analytics.export_to_json(log)
    assert json.loads(json_str) == []


# ── Layer 1e: Markdown exporter ──────────────────────────────────────────────


def test_v0628_export_to_markdown_has_h1_title() -> None:
    """The Markdown output has an H1 (#) title."""
    log = _make_log_with_entries()
    md = _analytics.export_to_markdown(log)
    assert md.startswith("# Quarantine Log Report")


def test_v0628_export_to_markdown_has_summary_section() -> None:
    """The Markdown output has a Summary section with the key counts."""
    log = _make_log_with_entries()
    md = _analytics.export_to_markdown(log)
    assert "## Summary" in md
    assert "**Total entries:**" in md
    assert "**Dropped:**" in md


def test_v0628_export_to_markdown_has_stage_table() -> None:
    """The Markdown output has a per-stage table."""
    log = _make_log_with_entries()
    md = _analytics.export_to_markdown(log)
    assert "## Per-stage breakdown" in md
    assert "| Stage | Total | Dropped | Recovered |" in md


def test_v0628_export_to_markdown_has_dropped_bullets_table() -> None:
    """The Markdown output has a table of dropped bullets."""
    log = _make_log_with_entries()
    md = _analytics.export_to_markdown(log)
    assert "## Dropped bullets" in md
    assert "| Bullet | Stage | Overlap |" in md


def test_v0628_export_to_markdown_empty_log() -> None:
    """An empty log produces a Markdown with the 'Empty quarantine log' message."""
    log = QuarantineLog(output_dir=None)
    md = _analytics.export_to_markdown(log)
    assert "Empty quarantine log" in md


# ── Layer 1f: dispatcher + registry ─────────────────────────────────────────


def test_v0628_export_quarantine_dispatcher_csv() -> None:
    """The export_quarantine() dispatcher routes 'csv' to export_to_csv."""
    log = _make_log_with_entries()
    assert _analytics.export_quarantine(log, "csv") == _analytics.export_to_csv(log)


def test_v0628_export_quarantine_dispatcher_json() -> None:
    """The export_quarantine() dispatcher routes 'json' to export_to_json."""
    log = _make_log_with_entries()
    assert _analytics.export_quarantine(log, "json") == _analytics.export_to_json(log)


def test_v0628_export_quarantine_dispatcher_markdown() -> None:
    """The export_quarantine() dispatcher routes 'markdown' to export_to_markdown."""
    log = _make_log_with_entries()
    assert _analytics.export_quarantine(log, "markdown") == _analytics.export_to_markdown(log)


def test_v0628_export_quarantine_unknown_format_raises() -> None:
    """An unknown format raises ValueError listing the available formats."""
    log = _make_log_with_entries()
    with pytest.raises(ValueError, match="Unknown quarantine export format"):
        _analytics.export_quarantine(log, "yaml")


def test_v0628_quarantine_export_formats_registry_has_three() -> None:
    """The QUARANTINE_EXPORT_FORMATS registry has exactly csv/json/markdown."""
    assert set(_analytics.QUARANTINE_EXPORT_FORMATS.keys()) == {"csv", "json", "markdown"}


def test_v0628_list_quarantine_formats_returns_all_three() -> None:
    """list_quarantine_formats() returns all 3 formats with descriptions."""
    formats = _analytics.list_quarantine_formats()
    names = [name for name, _desc in formats]
    assert set(names) == {"csv", "json", "markdown"}


def test_v0628_format_quarantine_formats_for_display_has_header() -> None:
    """The display formatter has the header + all 3 format names."""
    out = _analytics.format_quarantine_formats_for_display()
    assert "📤 Available Quarantine Export Formats" in out
    assert "csv" in out
    assert "json" in out
    assert "markdown" in out


# ── Layer 2: the summarisation CLI ───────────────────────────────────────────


def test_v0628_cli_stats_prints_statistics(tmp_path: Path) -> None:
    """The `stats` subcommand prints quarantine statistics to stdout."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(["stats", "--drops", str(drops_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📊 Quarantine Log Statistics" in out
    assert "Total entries:" in out
    assert "F4_source_overlap" in out


def test_v0628_cli_stats_missing_file_exits_2(tmp_path: Path) -> None:
    """The `stats` subcommand exits 2 if the drops file doesn't exist."""
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = _cli.main(["stats", "--drops", str(tmp_path / "nope.jsonl")])
    assert exit_code == 2


def test_v0628_cli_stats_empty_file_prints_empty_message(tmp_path: Path) -> None:
    """An empty drops file (no entries) prints the 'Empty quarantine log' message."""
    drops_path = tmp_path / "empty.jsonl"
    drops_path.write_text("", encoding="utf-8")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(["stats", "--drops", str(drops_path)])
    assert exit_code == 0
    assert "Empty quarantine log" in buf.getvalue()


def test_v0628_cli_export_list_mode_prints_all_formats(tmp_path: Path) -> None:
    """`export` without --format lists all available formats."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(["export", "--drops", str(drops_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📤 Available Quarantine Export Formats" in out
    for name in ("csv", "json", "markdown"):
        assert name in out


def test_v0628_cli_export_csv_to_file(tmp_path: Path) -> None:
    """`export --format csv --out FILE` writes the CSV to a file."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    out_path = tmp_path / "drops.csv"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(
            ["export", "--drops", str(drops_path), "--format", "csv", "--out", str(out_path)]
        )
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "bullet" in content  # header
    assert "F4_source_overlap" in content  # a stage


def test_v0628_cli_export_json_to_stdout(tmp_path: Path) -> None:
    """`export --format json` (no --out) prints the JSON to stdout."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(["export", "--drops", str(drops_path), "--format", "json"])
    assert exit_code == 0
    data = json.loads(buf.getvalue())  # must be valid JSON
    assert isinstance(data, list)
    assert len(data) == 5


def test_v0628_cli_export_markdown_to_file(tmp_path: Path) -> None:
    """`export --format markdown --out FILE` writes the Markdown report to a file."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    out_path = tmp_path / "drops.md"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(
            ["export", "--drops", str(drops_path), "--format", "markdown", "--out", str(out_path)]
        )
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "# Quarantine Log Report" in content
    assert "## Summary" in content


def test_v0628_cli_export_unknown_format_exits_1(tmp_path: Path) -> None:
    """An unknown --format exits 1 and lists the available formats."""
    log = _make_log_with_entries()
    drops_path = _write_drops_jsonl(tmp_path / "drops.jsonl", log.entries)
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = _cli.main(["export", "--drops", str(drops_path), "--format", "yaml"])
    assert exit_code == 1
    err = err_buf.getvalue()
    assert "yaml" in err
    assert "csv" in err  # available formats listed


def test_v0628_cli_export_missing_file_exits_2(tmp_path: Path) -> None:
    """A missing --drops file exits 2."""
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = _cli.main(
            ["export", "--drops", str(tmp_path / "nope.jsonl"), "--format", "csv"]
        )
    assert exit_code == 2


def test_v0628_cli_parser_has_stats_and_export_subcommands() -> None:
    """The CLI parser has 'stats' + 'export' subcommands (via Python API,
    not subprocess — the __init__.py tiktoken dependency makes subprocess
    fail; the Python API test is equivalent + faster)."""
    parser = _cli._build_parser()
    help_text = parser.format_help()
    assert "stats" in help_text
    assert "export" in help_text


# ── Layer 3: integration (QuarantineLog.add -> drops.jsonl -> CLI stats) ───


def test_v0628_integration_add_to_disk_then_cli_stats(tmp_path: Path) -> None:
    """Integration: add entries to a QuarantineLog with a real output_dir
    (writes drops.jsonl to disk), then run `stats` via the CLI. The round-trip
    must work — the CLI reads the same file the QuarantineLog wrote."""
    # Step 1: create a QuarantineLog with a real output_dir (writes to disk).
    log = QuarantineLog(output_dir=tmp_path)
    log.add("integration bullet 1", stage="F4_source_overlap", source_overlap=0.50)
    log.add("integration bullet 2", stage="B3_dedup", source_overlap=0.15)
    # Verify the drops.jsonl was written.
    drops_path = log.drops_path
    assert drops_path is not None
    assert drops_path.exists()

    # Step 2: run `stats` via the CLI on the written file.
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(["stats", "--drops", str(drops_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📊 Quarantine Log Statistics" in out
    assert "integration bullet 1" in out or "F4_source_overlap" in out


def test_v0628_integration_add_to_disk_then_cli_export_csv(tmp_path: Path) -> None:
    """Integration: add entries to disk, then export to CSV via the CLI."""
    log = QuarantineLog(output_dir=tmp_path)
    log.add("csv bullet", stage="F4", source_overlap=0.42)
    drops_path = log.drops_path

    out_path = tmp_path / "export.csv"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = _cli.main(
            ["export", "--drops", str(drops_path), "--format", "csv", "--out", str(out_path)]
        )
    assert exit_code == 0
    assert out_path.exists()
    csv_content = out_path.read_text(encoding="utf-8")
    assert "csv bullet" in csv_content
    assert "F4" in csv_content
