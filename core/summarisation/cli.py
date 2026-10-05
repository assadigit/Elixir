"""V0.6.28 (W-m2): headless summarisation CLI.

Why this exists
---------------
The summarisation module had NO CLI — the only way to interact with a
quarantine log (drops.jsonl) was through the Qt wizard's quarantine
view, or by writing Python code. This module gives the summarisation
module the same treatment the podcast module (V0.6.19) and translation
module (V0.6.27) got: a headless CLI.

Two subcommands:

  - ``stats --drops <FILE>`` — compute + print quarantine statistics
    (total entries, dropped vs recovered vs conservative, recovery rate,
    overlap distribution, per-stage + per-chapter breakdowns).
  - ``export --drops <FILE> [--format csv|json|markdown] [--out FILE]``
    — export the quarantine log to CSV (spreadsheet), JSON
    (programmatic), or Markdown (human-readable report).

The ``--drops`` argument points to a ``drops.jsonl`` file (the on-disk
format the QuarantineLog writes). The CLI reads the file via the
existing ``QuarantineLog.load_from_disk()`` static method, then
reconstructs QuarantineEntry objects for the analytics module.

Usage::

    python -m core.summarisation.cli stats --drops path/to/drops.jsonl
    python -m core.summarisation.cli export --drops path/to/drops.jsonl --format csv --out drops.csv
    python -m core.summarisation.cli export --drops path/to/drops.jsonl --format markdown

Exits 0 on success, 1 on unknown format, 2 on file/parse error.

NOTE: the CLI uses a deferred import for the analytics module (inside
the command handlers) to avoid importing core.summarisation.__init__
(which pulls in tiktoken) at module top. The quarantine module itself
is pure stdlib, so the deferred import is fast.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

logger = __name__  # placeholder; the CLI doesn't use logging


def _log_to_stdout(msg: str, level: str = "INFO") -> None:
    """The log callback the analytics module expects — prints to stdout."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level:7s}] {msg}", flush=True)


def _load_quarantine_log(drops_path: Path):
    """Load a drops.jsonl file + return a list-backed QuarantineLog-like
    object with an ``entries`` property + ``serialize()`` method.

    Uses QuarantineLog.load_from_disk() to read the JSONL, then
    reconstructs QuarantineEntry objects. Returns a minimal shim object
    that the analytics module can consume (it only needs .entries +
    .serialize()).

    Raises FileNotFoundError if the file doesn't exist.
    """
    # Deferred import — the quarantine module is pure stdlib, but
    # core.summarisation.__init__ imports Summarizer which pulls in
    # tiktoken. Importing quarantine.py directly avoids the chain.
    # We use importlib to load it from the file path, matching the
    # pattern in test_quarantine.py.
    import importlib.util

    _quarantine_path = Path(__file__).resolve().parent / "quarantine.py"
    _spec = importlib.util.spec_from_file_location(
        "core.summarisation.quarantine", _quarantine_path
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    # Read the drops.jsonl file via the static method.
    entry_dicts = _mod.QuarantineLog.load_from_disk(drops_path)
    if not entry_dicts:
        return _EntriesBackedLog([], _mod.QuarantineEntry)

    # Reconstruct QuarantineEntry objects from the dicts.
    entries = []
    for d in entry_dicts:
        entries.append(
            _mod.QuarantineEntry(
                bullet=d.get("bullet", ""),
                stage=d.get("stage", ""),
                threshold=d.get("threshold", 0.0),
                source_overlap=d.get("source_overlap", 0.0),
                reason=d.get("reason", ""),
                chapter=d.get("chapter", ""),
                actually_dropped=d.get("actually_dropped", True),
                recovered=d.get("recovered", False),
                timestamp=d.get("timestamp", 0.0),
            )
        )
    return _EntriesBackedLog(entries, _mod.QuarantineEntry)


class _EntriesBackedLog:
    """A minimal shim that the analytics module can consume.

    The analytics module only needs ``.entries`` (a list of
    QuarantineEntry) + ``.serialize()`` (a list of dicts). This shim
    provides both without needing a full QuarantineLog (which requires
    an output_dir + threading + the drops.jsonl path).

    This is a deliberate design choice — the analytics module's contract
    is "anything with .entries + .serialize()", not "a QuarantineLog
    instance". The shim makes the CLI's load-then-analyze flow clean.
    """

    def __init__(self, entries, entry_cls):
        self._entries = entries
        self._entry_cls = entry_cls

    @property
    def entries(self):
        return list(self._entries)  # snapshot copy

    def serialize(self):
        return [self._entry_cls_to_dict(e) for e in self._entries]

    def _entry_cls_to_dict(self, e):
        # QuarantineEntry.to_dict() does asdict + rounding; call it.
        if hasattr(e, "to_dict"):
            return e.to_dict()
        # Fallback — shouldn't happen for real QuarantineEntry objects.
        return {
            "bullet": e.bullet,
            "stage": e.stage,
            "threshold": e.threshold,
            "source_overlap": e.source_overlap,
            "reason": e.reason,
            "chapter": e.chapter,
            "actually_dropped": e.actually_dropped,
            "recovered": e.recovered,
            "timestamp": e.timestamp,
        }


def _cmd_stats(args: argparse.Namespace) -> int:
    """The stats subcommand — compute + print quarantine statistics."""
    # Deferred import of the analytics module — it imports from
    # core.summarisation.quarantine, which we load via importlib above.
    import importlib.util

    _analytics_path = Path(__file__).resolve().parent / "quarantine_analytics.py"
    _spec = importlib.util.spec_from_file_location(
        "core.summarisation.quarantine_analytics", _analytics_path
    )
    _analytics = importlib.util.module_from_spec(_spec)

    # We need the quarantine module loaded first (the analytics module
    # imports from it at module top). _load_quarantine_log loads it as
    # "core.summarisation.quarantine" — the analytics module's import
    # will find it in sys.modules.
    drops_path = Path(args.drops)
    if not drops_path.exists():
        print(f"❌ Drops file not found: {drops_path}", file=sys.stderr)
        return 2

    log_obj = _load_quarantine_log(drops_path)  # loads quarantine module too
    _spec.loader.exec_module(_analytics)  # now safe to exec the analytics module

    stats = _analytics.compute_quarantine_stats(log_obj)
    print(_analytics.format_quarantine_stats_for_display(stats, log=_log_to_stdout))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """The export subcommand — export a quarantine log to CSV/JSON/Markdown."""
    import importlib.util

    _analytics_path = Path(__file__).resolve().parent / "quarantine_analytics.py"
    _spec = importlib.util.spec_from_file_location(
        "core.summarisation.quarantine_analytics", _analytics_path
    )
    _analytics = importlib.util.module_from_spec(_spec)

    drops_path = Path(args.drops)
    if not drops_path.exists():
        print(f"❌ Drops file not found: {drops_path}", file=sys.stderr)
        return 2

    log_obj = _load_quarantine_log(drops_path)
    _spec.loader.exec_module(_analytics)

    if args.format is None:
        # List mode — print all available formats.
        print(_analytics.format_quarantine_formats_for_display(log=_log_to_stdout))
        return 0

    if args.format not in _analytics.QUARANTINE_EXPORT_FORMATS:
        available = ", ".join(sorted(_analytics.QUARANTINE_EXPORT_FORMATS.keys()))
        print(
            f"❌ Unknown format: {args.format!r}. Available: {available}.",
            file=sys.stderr,
        )
        return 1

    output = _analytics.export_quarantine(log_obj, args.format)

    if args.out is None:
        print(output, end="", flush=True)
        return 0

    out_path = Path(args.out)
    try:
        out_path.write_text(output, encoding="utf-8")
    except OSError as e:
        print(f"❌ Failed to write {out_path}: {e}", file=sys.stderr)
        return 2

    print(
        f"✅ Exported {args.format!r} ({len(log_obj.entries)} entries) to {out_path} "
        f"({len(output):,} bytes)."
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Subcommands: stats, export."""
    parser = argparse.ArgumentParser(
        prog="python -m core.summarisation.cli",
        description=(
            "V0.6.28 (W-m2): headless summarisation CLI. Computes quarantine "
            "log statistics and exports to CSV/JSON/Markdown without "
            "launching the Qt wizard."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # stats
    p_stats = sub.add_parser(
        "stats",
        help="Compute + print quarantine log statistics (entries, drops, recovery, overlap, stages, chapters).",
    )
    p_stats.add_argument("--drops", required=True, help="Path to the drops.jsonl file.")
    p_stats.set_defaults(func=_cmd_stats)

    # export
    p_export = sub.add_parser(
        "export",
        help="Export a quarantine log to CSV (spreadsheet), JSON (programmatic), or Markdown (human-readable).",
    )
    p_export.add_argument("--drops", required=True, help="Path to the drops.jsonl file.")
    p_export.add_argument(
        "--format",
        default=None,
        help="Export format (csv / json / markdown). Without this flag, lists all formats.",
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
