"""V0.6.27 — the translation glossary analytics + CLI batch pins.

This file pins the V0.6.27 additions — the FIRST round working on a
DIFFERENT module (translation) than the podcast module:

Layer 1 — the GLOSSARY ANALYTICS module (W-l1, NEW
core/translation/glossary_analytics.py):
  - ``compute_glossary_stats(glossary, top_n)`` — returns a
    ``GlossaryStats`` with total_entries / translated_count /
    untranslated_count / coverage_pct / entity_type_distribution /
    top_terms.
  - ``format_glossary_stats_for_display(stats, log)`` — multi-line
    formatter.
  - ``export_to_tsv(glossary)`` — TSV format (source TAB translation),
    the standard CAT-tool glossary format.
  - ``export_to_csv(glossary)`` — CSV format (source, translation,
    entity_type, frequency), for spreadsheet tools.
  - ``export_to_json(glossary)`` — wraps the existing to_dict().
  - ``GLOSSARY_EXPORT_FORMATS`` registry + ``export_glossary()``
    dispatcher.

Layer 2 — the translation CLI (W-l2, NEW core/translation/cli.py):
  - ``stats`` subcommand: prints glossary statistics.
  - ``export`` subcommand: lists all formats, or exports to
    stdout/file with ``--format <NAME> [--out FILE]``.
  - Exits 0 on success, 1 on unknown format, 2 on file/parse error.

All tests are pure-Python (no PySide6 / no torch / no spaCy).
"""

from __future__ import annotations

import contextlib
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── helpers ────────────────────────────────────────────────────────────────


def _make_glossary():
    """A Glossary with a mix of translated/untranslated + entity types."""
    from core.translation.glossary import Glossary, GlossaryEntry

    g = Glossary(source_lang="en", target_lang="fa")
    g.entries["mark manson"] = GlossaryEntry(
        source="Mark Manson", translation="مارک منسون", entity_type="PERSON", frequency=15
    )
    g.entries["atomic habits"] = GlossaryEntry(
        source="Atomic Habits", translation="عادت‌های اتمی", entity_type="WORK_OF_ART", frequency=8
    )
    g.entries["google"] = GlossaryEntry(
        source="Google", translation="گوگل", entity_type="ORG", frequency=5
    )
    g.entries["new york"] = GlossaryEntry(
        source="New York", translation="نیویورک", entity_type="GPE", frequency=3
    )
    g.entries["unknown term"] = GlossaryEntry(
        source="Unknown Term", translation="", entity_type="TERM", frequency=2
    )
    return g


def _write_glossary_json(path: Path) -> Path:
    """Write the test glossary to a JSON file."""
    g = _make_glossary()
    path.write_text(json.dumps(g.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Layer 1a: compute_glossary_stats ─────────────────────────────────────────


def test_v0627_compute_stats_empty_glossary() -> None:
    """An empty glossary produces zero-stats (total=0, coverage=0)."""
    from core.translation.glossary import Glossary
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(Glossary())
    assert stats.is_empty is True
    assert stats.total_entries == 0
    assert stats.translated_count == 0
    assert stats.untranslated_count == 0
    assert stats.coverage_pct == 0.0
    assert stats.entity_type_distribution == {}
    assert stats.top_terms == []


def test_v0627_compute_stats_total_entries() -> None:
    """The total_entries count matches the glossary's entry count."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary())
    assert stats.total_entries == 5


def test_v0627_compute_stats_translated_vs_untranslated() -> None:
    """The translated/untranslated counts are correct (4 translated, 1
    untranslated in the test glossary)."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary())
    assert stats.translated_count == 4
    assert stats.untranslated_count == 1


def test_v0627_compute_stats_coverage_pct() -> None:
    """The coverage_pct is (translated / total * 100) = (4/5*100) = 80%."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary())
    assert stats.coverage_pct == pytest.approx(80.0)


def test_v0627_compute_stats_entity_type_distribution() -> None:
    """The entity_type_distribution has the right counts per type."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary())
    dist = stats.entity_type_distribution
    assert dist.get("PERSON") == 1
    assert dist.get("WORK_OF_ART") == 1
    assert dist.get("ORG") == 1
    assert dist.get("GPE") == 1
    assert dist.get("TERM") == 1


def test_v0627_compute_stats_top_terms_sorted_by_frequency() -> None:
    """The top_terms are sorted by frequency (desc) — the most-frequent
    term is first."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary(), top_n=3)
    assert len(stats.top_terms) == 3
    assert stats.top_terms[0].source == "Mark Manson"  # frequency=15
    assert stats.top_terms[1].source == "Atomic Habits"  # frequency=8
    assert stats.top_terms[2].source == "Google"  # frequency=5


def test_v0627_compute_stats_top_n_limit() -> None:
    """The top_n parameter limits the number of top terms returned."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary(), top_n=2)
    assert len(stats.top_terms) == 2


def test_v0627_compute_stats_languages_echoed() -> None:
    """The source_lang + target_lang are echoed from the glossary."""
    from core.translation.glossary_analytics import compute_glossary_stats

    stats = compute_glossary_stats(_make_glossary())
    assert stats.source_lang == "en"
    assert stats.target_lang == "fa"


# ── Layer 1b: format_glossary_stats_for_display ──────────────────────────────


def test_v0627_format_stats_empty_glossary_message() -> None:
    """An empty glossary's display is the '⚠️ Empty glossary' message."""
    from core.translation.glossary import Glossary
    from core.translation.glossary_analytics import (
        compute_glossary_stats,
        format_glossary_stats_for_display,
    )

    stats = compute_glossary_stats(Glossary())
    out = format_glossary_stats_for_display(stats)
    assert "⚠️" in out
    assert "Empty glossary" in out


def test_v0627_format_stats_has_all_sections() -> None:
    """A populated glossary's display has all the expected sections."""
    from core.translation.glossary_analytics import (
        compute_glossary_stats,
        format_glossary_stats_for_display,
    )

    stats = compute_glossary_stats(_make_glossary())
    out = format_glossary_stats_for_display(stats)
    assert "📊 Glossary Statistics" in out
    assert "Languages:" in out
    assert "Total entries:" in out
    assert "Translated:" in out
    assert "Untranslated:" in out
    assert "Entity type distribution:" in out
    assert "Top" in out and "terms" in out
    # The actual terms should appear.
    assert "Mark Manson" in out
    assert "Atomic Habits" in out


def test_v0627_format_stats_log_callback() -> None:
    """The log callback is called for each output line."""
    from core.translation.glossary_analytics import (
        compute_glossary_stats,
        format_glossary_stats_for_display,
    )

    stats = compute_glossary_stats(_make_glossary())
    logs: list[tuple[str, str]] = []
    format_glossary_stats_for_display(stats, log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0


# ── Layer 1c: TSV exporter ─────────────────────────────────────────────────


def test_v0627_export_to_tsv_has_tab_separator() -> None:
    """The TSV output uses TAB as the field separator."""
    from core.translation.glossary_analytics import export_to_tsv

    tsv = export_to_tsv(_make_glossary())
    assert "\t" in tsv


def test_v0627_export_to_tsv_has_all_entries() -> None:
    """The TSV output has one line per glossary entry."""
    from core.translation.glossary_analytics import export_to_tsv

    tsv = export_to_tsv(_make_glossary())
    lines = tsv.strip().split("\n")
    assert len(lines) == 5  # 5 entries


def test_v0627_export_to_tsv_sorted_by_frequency() -> None:
    """The TSV output is sorted by frequency (desc) — the most-frequent
    term is first."""
    from core.translation.glossary_analytics import export_to_tsv

    tsv = export_to_tsv(_make_glossary())
    first_line = tsv.strip().split("\n")[0]
    assert "Mark Manson" in first_line  # frequency=15, highest


def test_v0627_export_to_tsv_untranslated_has_empty_translation() -> None:
    """An untranslated term has an empty translation field in the TSV
    (source TAB empty)."""
    from core.translation.glossary_analytics import export_to_tsv

    tsv = export_to_tsv(_make_glossary())
    # Check the raw TSV string (not the stripped lines) — the untranslated
    # term's line has a trailing tab before the newline. Using 'in' avoids
    # the .strip() issue that removes trailing tabs from the last line.
    assert "Unknown Term\t" in tsv


def test_v0627_export_to_tsv_empty_glossary_returns_empty_string() -> None:
    """An empty glossary produces an empty TSV string."""
    from core.translation.glossary import Glossary
    from core.translation.glossary_analytics import export_to_tsv

    assert export_to_tsv(Glossary()) == ""


# ── Layer 1d: CSV exporter ──────────────────────────────────────────────────


def test_v0627_export_to_csv_has_header_row() -> None:
    """The CSV output has a header row (source, translation, entity_type, frequency)."""
    from core.translation.glossary_analytics import export_to_csv

    csv_str = export_to_csv(_make_glossary())
    first_line = csv_str.strip().split("\n")[0]
    assert "source" in first_line
    assert "translation" in first_line
    assert "entity_type" in first_line
    assert "frequency" in first_line


def test_v0627_export_to_csv_has_all_entries() -> None:
    """The CSV output has a header + one row per entry (5+1=6 lines)."""
    from core.translation.glossary_analytics import export_to_csv

    csv_str = export_to_csv(_make_glossary())
    lines = csv_str.strip().split("\n")
    assert len(lines) == 6  # header + 5 entries


def test_v0627_export_to_csv_sorted_by_frequency() -> None:
    """The CSV output is sorted by frequency (desc)."""
    from core.translation.glossary_analytics import export_to_csv

    csv_str = export_to_csv(_make_glossary())
    lines = csv_str.strip().split("\n")
    # The second line (index 1, after the header) should be the highest-frequency.
    assert "Mark Manson" in lines[1]


def test_v0627_export_to_csv_empty_glossary_has_header_only() -> None:
    """An empty glossary produces a CSV with just the header row."""
    from core.translation.glossary import Glossary
    from core.translation.glossary_analytics import export_to_csv

    csv_str = export_to_csv(Glossary())
    lines = csv_str.strip().split("\n")
    assert len(lines) == 1  # just the header
    assert "source" in lines[0]


def test_v0627_export_to_csv_handles_commas_in_source() -> None:
    """A source term with a comma is properly quoted in the CSV output
    (csv.QUOTE_MINIMAL handles this)."""
    from core.translation.glossary import Glossary, GlossaryEntry
    from core.translation.glossary_analytics import export_to_csv

    g = Glossary()
    g.entries["hello, world"] = GlossaryEntry(
        source="Hello, World", translation="سلام، دنیا", entity_type="TERM", frequency=1
    )
    csv_str = export_to_csv(g)
    # The source with a comma must be quoted.
    assert '"Hello, World"' in csv_str


# ── Layer 1e: JSON exporter ──────────────────────────────────────────────────


def test_v0627_export_to_json_is_valid_json() -> None:
    """The JSON output is valid JSON (parseable)."""
    from core.translation.glossary_analytics import export_to_json

    json_str = export_to_json(_make_glossary())
    data = json.loads(json_str)  # must not raise
    assert "entries" in data
    assert "source_lang" in data
    assert "target_lang" in data


def test_v0627_export_to_json_matches_to_dict() -> None:
    """The JSON exporter wraps to_dict() — the parsed JSON matches."""
    from core.translation.glossary_analytics import export_to_json

    g = _make_glossary()
    json_str = export_to_json(g)
    parsed = json.loads(json_str)
    assert parsed == g.to_dict()


# ── Layer 1f: dispatcher + registry ─────────────────────────────────────────


def test_v0627_export_glossary_dispatcher_tsv() -> None:
    """The export_glossary() dispatcher routes 'tsv' to export_to_tsv."""
    from core.translation.glossary_analytics import export_glossary, export_to_tsv

    g = _make_glossary()
    assert export_glossary(g, "tsv") == export_to_tsv(g)


def test_v0627_export_glossary_dispatcher_csv() -> None:
    """The export_glossary() dispatcher routes 'csv' to export_to_csv."""
    from core.translation.glossary_analytics import export_glossary, export_to_csv

    g = _make_glossary()
    assert export_glossary(g, "csv") == export_to_csv(g)


def test_v0627_export_glossary_dispatcher_json() -> None:
    """The export_glossary() dispatcher routes 'json' to export_to_json."""
    from core.translation.glossary_analytics import export_glossary, export_to_json

    g = _make_glossary()
    assert export_glossary(g, "json") == export_to_json(g)


def test_v0627_export_glossary_unknown_format_raises() -> None:
    """An unknown format raises ValueError listing the available formats."""
    from core.translation.glossary_analytics import export_glossary

    with pytest.raises(ValueError, match="Unknown glossary export format"):
        export_glossary(_make_glossary(), "yaml")


def test_v0627_glossary_export_formats_registry_has_three() -> None:
    """The GLOSSARY_EXPORT_FORMATS registry has exactly tsv/csv/json."""
    from core.translation.glossary_analytics import GLOSSARY_EXPORT_FORMATS

    assert set(GLOSSARY_EXPORT_FORMATS.keys()) == {"tsv", "csv", "json"}


def test_v0627_list_glossary_formats_returns_all_three() -> None:
    """list_glossary_formats() returns all 3 formats with descriptions."""
    from core.translation.glossary_analytics import list_glossary_formats

    formats = list_glossary_formats()
    names = [name for name, _desc in formats]
    assert set(names) == {"tsv", "csv", "json"}


def test_v0627_format_glossary_formats_for_display_has_header() -> None:
    """The display formatter has the header + all 3 format names."""
    from core.translation.glossary_analytics import format_glossary_formats_for_display

    out = format_glossary_formats_for_display()
    assert "📤 Available Glossary Export Formats" in out
    assert "tsv" in out
    assert "csv" in out
    assert "json" in out


# ── Layer 2: the translation CLI ────────────────────────────────────────────


def test_v0627_cli_stats_prints_statistics(tmp_path: Path) -> None:
    """The `stats` subcommand prints glossary statistics to stdout."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["stats", "--glossary", str(glossary_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📊 Glossary Statistics" in out
    assert "Total entries:" in out
    assert "Mark Manson" in out


def test_v0627_cli_stats_missing_file_exits_2(tmp_path: Path) -> None:
    """The `stats` subcommand exits 2 if the glossary file doesn't exist."""
    from core.translation.cli import main as cli_main

    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["stats", "--glossary", str(tmp_path / "nope.json")])
    assert exit_code == 2
    assert "not found" in err_buf.getvalue().lower() or "❌" in err_buf.getvalue()


def test_v0627_cli_stats_bad_json_exits_2(tmp_path: Path) -> None:
    """The `stats` subcommand exits 2 on malformed JSON."""
    from core.translation.cli import main as cli_main

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not json", encoding="utf-8")
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["stats", "--glossary", str(bad_path)])
    assert exit_code == 2


def test_v0627_cli_stats_top_n_flag(tmp_path: Path) -> None:
    """The --top-n flag limits the number of top terms shown."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["stats", "--glossary", str(glossary_path), "--top-n", "2"])
    out = buf.getvalue()
    assert "Top 2 terms" in out


def test_v0627_cli_export_list_mode_prints_all_formats(tmp_path: Path) -> None:
    """`export` without --format lists all available formats."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["export", "--glossary", str(glossary_path)])
    assert exit_code == 0
    out = buf.getvalue()
    assert "📤 Available Glossary Export Formats" in out
    for name in ("tsv", "csv", "json"):
        assert name in out


def test_v0627_cli_export_tsv_to_stdout(tmp_path: Path) -> None:
    """`export --format tsv` prints the TSV to stdout."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["export", "--glossary", str(glossary_path), "--format", "tsv"])
    assert exit_code == 0
    out = buf.getvalue()
    assert "\t" in out  # TSV has tabs
    assert "Mark Manson" in out


def test_v0627_cli_export_csv_to_file(tmp_path: Path) -> None:
    """`export --format csv --out FILE` writes the CSV to a file."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    out_path = tmp_path / "glossary.csv"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(
            [
                "export",
                "--glossary",
                str(glossary_path),
                "--format",
                "csv",
                "--out",
                str(out_path),
            ]
        )
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "source,translation,entity_type,frequency" in content
    assert "Mark Manson" in content


def test_v0627_cli_export_json_to_file(tmp_path: Path) -> None:
    """`export --format json --out FILE` writes JSON to a file."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    out_path = tmp_path / "glossary_out.json"
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(
            [
                "export",
                "--glossary",
                str(glossary_path),
                "--format",
                "json",
                "--out",
                str(out_path),
            ]
        )
    assert exit_code == 0
    assert out_path.exists()
    # The output must be valid JSON.
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "entries" in data


def test_v0627_cli_export_unknown_format_exits_1(tmp_path: Path) -> None:
    """An unknown --format exits 1 and lists the available formats."""
    from core.translation.cli import main as cli_main

    glossary_path = _write_glossary_json(tmp_path / "glossary.json")
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["export", "--glossary", str(glossary_path), "--format", "yaml"])
    assert exit_code == 1
    err = err_buf.getvalue()
    assert "yaml" in err
    assert "tsv" in err  # available formats listed


def test_v0627_cli_export_missing_file_exits_2(tmp_path: Path) -> None:
    """A missing --glossary file exits 2."""
    from core.translation.cli import main as cli_main

    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(
            [
                "export",
                "--glossary",
                str(tmp_path / "nope.json"),
                "--format",
                "tsv",
            ]
        )
    assert exit_code == 2


def test_v0627_cli_export_bad_json_exits_2(tmp_path: Path) -> None:
    """A malformed glossary JSON exits 2."""
    from core.translation.cli import main as cli_main

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not json", encoding="utf-8")
    err_buf = StringIO()
    with contextlib.redirect_stderr(err_buf):
        exit_code = cli_main(["export", "--glossary", str(bad_path), "--format", "tsv"])
    assert exit_code == 2


def test_v0627_cli_module_invocable_via_python_m() -> None:
    """The CLI must have the right subcommands — verified via the Python API
    (not subprocess, which would trigger core.translation.__init__.py and its
    tiktoken dependency)."""
    from core.translation.cli import _build_parser

    parser = _build_parser()
    # The parser must accept 'stats' and 'export' as subcommands.
    # We verify by parsing --help output from the parser's actions.
    help_text = parser.format_help()
    assert "stats" in help_text
    assert "export" in help_text


# ── Layer 3: integration (glossary save -> CLI stats -> CLI export) ────────


def test_v0627_integration_save_then_stats_then_export(tmp_path: Path) -> None:
    """Integration: save a glossary to JSON via Glossary.save(), then run
    `stats` + `export` via the CLI. The round-trip must work."""
    from core.translation.cli import main as cli_main
    from core.translation.glossary import Glossary, GlossaryEntry

    # Step 1: create + save a glossary via the production save() method.
    g = Glossary(source_lang="en", target_lang="fa")
    g.entries["test term"] = GlossaryEntry(
        source="Test Term", translation="اصطلاح آزمایشی", entity_type="TERM", frequency=3
    )
    glossary_path = tmp_path / "glossary.json"
    g.save(glossary_path)
    assert glossary_path.exists()

    # Step 2: run `stats` via the CLI.
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["stats", "--glossary", str(glossary_path)])
    assert exit_code == 0
    assert "Test Term" in buf.getvalue()

    # Step 3: run `export --format tsv` via the CLI.
    out_path = tmp_path / "glossary.tsv"
    buf2 = StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code = cli_main(
            [
                "export",
                "--glossary",
                str(glossary_path),
                "--format",
                "tsv",
                "--out",
                str(out_path),
            ]
        )
    assert exit_code == 0
    assert out_path.exists()
    tsv_content = out_path.read_text(encoding="utf-8")
    assert "Test Term" in tsv_content
    assert "اصطلاح آزمایشی" in tsv_content
