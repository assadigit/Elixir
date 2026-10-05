"""V0.6.27 (W-l2): headless translation CLI.

Why this exists
---------------
The podcast module got a headless CLI (V0.6.19, `core.podcast.cli`)
with seven subcommands covering the full script lifecycle. The
translation module had NO CLI — the only way to interact with a
glossary was through the Qt wizard or by writing Python code.

This module gives the translation module the same treatment, starting
with two subcommands:

  - ``stats`` — compute + print glossary statistics (total entries,
    translated vs untranslated, entity type distribution, top-N terms).
  - ``export`` — export a glossary to TSV (CAT-tool format), CSV
    (spreadsheet), or JSON.

The glossary JSON file is the same format ``Glossary.save()`` writes
(source_lang, target_lang, entries dict) — the same format the Qt
wizard produces.

Usage::

    python -m core.translation.cli stats --glossary glossary.json
    python -m core.translation.cli export --glossary glossary.json --format tsv --out glossary.tsv
    python -m core.translation.cli export --glossary glossary.json --format csv

Exits 0 on success, 1 on unknown format, 2 on file/parse error.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from core.translation.glossary import Glossary

logger = __name__  # placeholder; the CLI doesn't use logging


def _log_to_stdout(msg: str, level: str = "INFO") -> None:
    """The log callback the analytics module expects — prints to stdout."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level:7s}] {msg}", flush=True)


def _load_glossary(path: Path) -> Glossary:
    """Load a Glossary from a JSON file. Raises on file/parse error."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return Glossary.from_dict(data)


def _cmd_stats(args: argparse.Namespace) -> int:
    """The stats subcommand — compute + print glossary statistics."""
    from core.translation.glossary_analytics import (
        compute_glossary_stats,
        format_glossary_stats_for_display,
    )

    glossary_path = Path(args.glossary)
    if not glossary_path.exists():
        print(f"❌ Glossary file not found: {glossary_path}", file=sys.stderr)
        return 2
    try:
        glossary = _load_glossary(glossary_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse glossary JSON: {e}", file=sys.stderr)
        return 2

    stats = compute_glossary_stats(glossary, top_n=args.top_n)
    print(format_glossary_stats_for_display(stats, log=_log_to_stdout))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """The export subcommand — export a glossary to TSV/CSV/JSON."""
    from core.translation.glossary_analytics import (
        GLOSSARY_EXPORT_FORMATS,
        export_glossary,
        format_glossary_formats_for_display,
    )

    if args.format is None:
        # List mode — print all available formats.
        print(format_glossary_formats_for_display(log=_log_to_stdout))
        return 0

    if args.format not in GLOSSARY_EXPORT_FORMATS:
        print(
            f"❌ Unknown format: {args.format!r}. Available: "
            f"{', '.join(sorted(GLOSSARY_EXPORT_FORMATS.keys()))}.",
            file=sys.stderr,
        )
        return 1

    glossary_path = Path(args.glossary)
    if not glossary_path.exists():
        print(f"❌ Glossary file not found: {glossary_path}", file=sys.stderr)
        return 2
    try:
        glossary = _load_glossary(glossary_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse glossary JSON: {e}", file=sys.stderr)
        return 2

    output = export_glossary(glossary, args.format)

    if args.out is None:
        # Print to stdout.
        print(output, end="", flush=True)
        return 0

    out_path = Path(args.out)
    try:
        out_path.write_text(output, encoding="utf-8")
    except OSError as e:
        print(f"❌ Failed to write {out_path}: {e}", file=sys.stderr)
        return 2

    print(
        f"✅ Exported {args.format!r} ({len(glossary.entries)} entries) to {out_path} "
        f"({len(output):,} bytes)."
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Subcommands: stats, export."""
    parser = argparse.ArgumentParser(
        prog="python -m core.translation.cli",
        description=(
            "V0.6.27 (W-l2): headless translation CLI. Computes glossary "
            "statistics and exports to TSV/CSV/JSON without launching the "
            "Qt wizard."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # stats
    p_stats = sub.add_parser(
        "stats",
        help="Compute + print glossary statistics (entries, coverage, entity types, top terms).",
    )
    p_stats.add_argument("--glossary", required=True, help="Path to the glossary JSON file.")
    p_stats.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="How many top-frequency terms to show (default 10).",
    )
    p_stats.set_defaults(func=_cmd_stats)

    # export
    p_export = sub.add_parser(
        "export",
        help="Export a glossary to TSV (CAT-tool), CSV (spreadsheet), or JSON.",
    )
    p_export.add_argument("--glossary", required=True, help="Path to the glossary JSON file.")
    p_export.add_argument(
        "--format",
        default=None,
        help="Export format (tsv / csv / json). Without this flag, lists all formats.",
    )
    p_export.add_argument(
        "--out",
        default=None,
        help="Output file path (without this, prints to stdout).",
    )
    p_export.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    """The CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
