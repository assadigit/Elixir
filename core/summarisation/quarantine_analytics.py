"""V0.6.28 (W-m1): quarantine log analytics + export.

Why this exists
---------------
The summarisation module's ``QuarantineLog`` (V10.28.0) tracks every
bullet dropped by the anti-hallucination pipeline, with 10 fields per
entry (bullet, stage, threshold, source_overlap, reason, chapter,
actually_dropped, recovered, timestamp). It has a ``summary()`` method
that returns a ``{stage: count}`` breakdown — useful, but minimal.

The operator who wants to understand the quarantine log needs richer
analytics:

  - How many bullets were dropped vs recovered vs conservative-logged?
  - What's the recovery rate (recovered / dropped)?
  - What's the per-stage breakdown WITH recovery counts (not just total)?
  - What's the per-chapter breakdown (which chapters lost the most)?
  - What's the source_overlap distribution (min / max / avg / median)?
  - Which stages have the highest overlap (candidates for threshold tuning)?

And the operator who wants to share the quarantine log (e.g., in a bug
report, a code review, an audit) needs export to:

  - **CSV** — for spreadsheet analysis (one row per entry, all 10 fields).
  - **JSON** — the full ``serialize()`` output (a list of dicts), for
    programmatic consumption.
  - **Markdown** — a human-readable report with the stats + a table of
    the dropped bullets, for pasting into a GitHub issue or a code review.

This module fills both gaps. Pure-Python (no PySide6 / no torch / no
numpy — uses stdlib ``statistics`` for the overlap distribution).

Public API:
  - ``compute_quarantine_stats(log)`` — returns a ``QuarantineStats``.
  - ``format_quarantine_stats_for_display(stats, log)`` — multi-line formatter.
  - ``export_to_csv(log)`` — CSV with all 10 fields + a header row.
  - ``export_to_json(log)`` — wraps the existing ``serialize()``.
  - ``export_to_markdown(log)`` — a human-readable Markdown report.
  - ``QUARANTINE_EXPORT_FORMATS`` + ``export_quarantine()`` dispatcher.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

# The analytics module imports from core.summarisation.quarantine. The
# caller (the CLI / tests) is responsible for ensuring the import works
# — the quarantine module itself is pure stdlib, but
# core.summarisation.__init__ imports Summarizer which pulls in tiktoken
# (not installed in every sandbox). The existing test_quarantine.py
# loads the module via importlib.util to bypass this; the analytics
# module uses a normal import (the CLI's deferred-import pattern avoids
# the issue at runtime; the tests use the importlib workaround if needed).
from core.summarisation.quarantine import QuarantineEntry, QuarantineLog

# ── QuarantineStats ─────────────────────────────────────────────────────────


@dataclass
class StageBreakdown:
    """Per-stage statistics (one per unique stage name)."""

    stage: str
    total: int = 0
    dropped: int = 0  # actually_dropped=True
    conservative: int = 0  # actually_dropped=False (logged but kept)
    recovered: int = 0  # recovered=True
    avg_overlap: float = 0.0  # mean source_overlap for this stage's entries


@dataclass
class ChapterBreakdown:
    """Per-chapter statistics (one per unique chapter heading)."""

    chapter: str
    total: int = 0
    dropped: int = 0
    recovered: int = 0


@dataclass
class QuarantineStats:
    """Statistics for a QuarantineLog.

    All counts are computed from the log's entries. The ``recovery_rate``
    is (recovered_count / dropped_count) — 0.0 if no drops.
    """

    total_entries: int = 0
    dropped_count: int = 0  # actually_dropped=True
    conservative_count: int = 0  # actually_dropped=False
    recovered_count: int = 0  # recovered=True
    recovery_rate: float = 0.0  # recovered / dropped, 0 if no drops

    # Overlap distribution (across ALL entries).
    overlap_min: float = 0.0
    overlap_max: float = 0.0
    overlap_mean: float = 0.0
    overlap_median: float = 0.0

    # Per-stage + per-chapter breakdowns.
    stage_breakdown: list[StageBreakdown] = field(default_factory=list)
    chapter_breakdown: list[ChapterBreakdown] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True iff the log has no entries."""
        return self.total_entries == 0


def compute_quarantine_stats(log: QuarantineLog) -> QuarantineStats:
    """Compute statistics for a QuarantineLog.

    Args:
        log: the QuarantineLog to analyze.

    Returns:
        A QuarantineStats with all fields populated.
    """
    entries = log.entries  # thread-safe snapshot
    total = len(entries)
    if total == 0:
        return QuarantineStats()

    dropped = sum(1 for e in entries if e.actually_dropped)
    conservative = total - dropped
    recovered = sum(1 for e in entries if e.recovered)
    recovery_rate = (recovered / dropped) if dropped > 0 else 0.0

    # Overlap distribution (across all entries — conservative-logged entries
    # have an overlap too, useful for tuning thresholds).
    overlaps = [e.source_overlap for e in entries if e.source_overlap > 0]
    if overlaps:
        overlap_min = min(overlaps)
        overlap_max = max(overlaps)
        overlap_mean = statistics.mean(overlaps)
        overlap_median = statistics.median(overlaps)
    else:
        overlap_min = overlap_max = overlap_mean = overlap_median = 0.0

    # Per-stage breakdown — group by stage, count dropped/conservative/recovered.
    stage_map: dict[str, StageBreakdown] = {}
    for e in entries:
        sb = stage_map.setdefault(e.stage, StageBreakdown(stage=e.stage))
        sb.total += 1
        if e.actually_dropped:
            sb.dropped += 1
        else:
            sb.conservative += 1
        if e.recovered:
            sb.recovered += 1
    # Compute avg_overlap per stage.
    stage_overlaps: dict[str, list[float]] = {}
    for e in entries:
        if e.source_overlap > 0:
            stage_overlaps.setdefault(e.stage, []).append(e.source_overlap)
    for stage, sb in stage_map.items():
        overlaps_for_stage = stage_overlaps.get(stage, [])
        sb.avg_overlap = statistics.mean(overlaps_for_stage) if overlaps_for_stage else 0.0
    # Sort stage_breakdown by total (desc) then stage name (asc) for determinism.
    stage_list = sorted(stage_map.values(), key=lambda s: (-s.total, s.stage))

    # Per-chapter breakdown — group by chapter (empty string for unknown).
    chapter_map: dict[str, ChapterBreakdown] = {}
    for e in entries:
        ch = e.chapter or "(unknown)"
        cb = chapter_map.setdefault(ch, ChapterBreakdown(chapter=ch))
        cb.total += 1
        if e.actually_dropped:
            cb.dropped += 1
        if e.recovered:
            cb.recovered += 1
    chapter_list = sorted(chapter_map.values(), key=lambda c: (-c.total, c.chapter))

    return QuarantineStats(
        total_entries=total,
        dropped_count=dropped,
        conservative_count=conservative,
        recovered_count=recovered,
        recovery_rate=recovery_rate,
        overlap_min=overlap_min,
        overlap_max=overlap_max,
        overlap_mean=overlap_mean,
        overlap_median=overlap_median,
        stage_breakdown=stage_list,
        chapter_breakdown=chapter_list,
    )


def format_quarantine_stats_for_display(
    stats: QuarantineStats,
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format a QuarantineStats as a multi-line string.

    The format::

        📊 Quarantine Log Statistics
        ════════════════════════════════════════════════════════════
        Total entries:      42
        Dropped:            35
        Conservative:         3  (logged but kept)
        Recovered:           7  (20% recovery rate)

        📈 Source overlap distribution:
            Min:    0.05
            Max:    0.92
            Mean:   0.31
            Median: 0.28

        🏷️ Per-stage breakdown:
            F4_source_overlap:    18 total, 15 dropped, 3 recovered (avg overlap 0.42)
            B3_dedup:             12 total, 12 dropped, 2 recovered (avg overlap 0.18)
            ...

        📑 Per-chapter breakdown:
            Chapter 1:    8 total, 7 dropped, 1 recovered
            Chapter 2:    5 total, 4 dropped, 2 recovered
            ...

    If the log is empty, returns "✅ Empty quarantine log — no drops to report.".
    """
    if stats.is_empty:
        msg = "✅ Empty quarantine log — no drops to report."
        if log:
            log(msg, "INFO")
        return msg

    parts: list[str] = []
    parts.append("📊 Quarantine Log Statistics")
    parts.append("═" * 60)
    parts.append(f"Total entries:      {stats.total_entries}")
    parts.append(f"Dropped:            {stats.dropped_count}")
    parts.append(f"Conservative:       {stats.conservative_count}  (logged but kept)")
    recovery_pct = stats.recovery_rate * 100
    parts.append(
        f"Recovered:          {stats.recovered_count}  ({recovery_pct:.0f}% recovery rate)"
    )
    parts.append("")
    parts.append("📈 Source overlap distribution:")
    parts.append(f"    Min:    {stats.overlap_min:.4f}")
    parts.append(f"    Max:    {stats.overlap_max:.4f}")
    parts.append(f"    Mean:   {stats.overlap_mean:.4f}")
    parts.append(f"    Median: {stats.overlap_median:.4f}")
    parts.append("")
    parts.append("🏷️ Per-stage breakdown:")
    for sb in stats.stage_breakdown:
        parts.append(
            f"    {sb.stage:30s}: {sb.total:3d} total, {sb.dropped:3d} dropped, "
            f"{sb.recovered:3d} recovered (avg overlap {sb.avg_overlap:.4f})"
        )
    parts.append("")
    parts.append("📑 Per-chapter breakdown:")
    for cb in stats.chapter_breakdown:
        parts.append(
            f"    {cb.chapter:30s}: {cb.total:3d} total, {cb.dropped:3d} dropped, "
            f"{cb.recovered:3d} recovered"
        )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out


# ── Exporters ────────────────────────────────────────────────────────────────


def export_to_csv(log: QuarantineLog) -> str:
    """Export a QuarantineLog to CSV — one row per entry, all 10 fields,
    with a header row. For spreadsheet analysis (Excel, Google Sheets).

    Args:
        log: the QuarantineLog to export.

    Returns:
        A CSV string. Empty log → just the header row.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(
        [
            "bullet",
            "stage",
            "threshold",
            "source_overlap",
            "reason",
            "chapter",
            "actually_dropped",
            "recovered",
            "timestamp",
        ]
    )
    for e in log.entries:
        writer.writerow(
            [
                e.bullet,
                e.stage,
                round(float(e.threshold), 4),
                round(float(e.source_overlap), 4),
                e.reason,
                e.chapter,
                e.actually_dropped,
                e.recovered,
                round(float(e.timestamp), 3),
            ]
        )
    return buf.getvalue()


def export_to_json(log: QuarantineLog) -> str:
    """Export a QuarantineLog to JSON — wraps the existing ``serialize()``
    (a list of entry dicts). For programmatic consumption.

    Args:
        log: the QuarantineLog to export.

    Returns:
        A JSON string (indented, ensure_ascii=False).
    """
    return json.dumps(log.serialize(), indent=2, ensure_ascii=False)


def export_to_markdown(log: QuarantineLog) -> str:
    """Export a QuarantineLog to Markdown — a human-readable report with
    the stats + a table of the dropped bullets. For pasting into a GitHub
    issue or a code review.

    Args:
        log: the QuarantineLog to export.

    Returns:
        A Markdown string.
    """
    stats = compute_quarantine_stats(log)
    parts: list[str] = ["# Quarantine Log Report", ""]

    if stats.is_empty:
        parts.append("✅ Empty quarantine log — no drops to report.")
        return "\n".join(parts)

    # Summary section.
    parts.append("## Summary")
    parts.append("")
    parts.append(f"- **Total entries:** {stats.total_entries}")
    parts.append(f"- **Dropped:** {stats.dropped_count}")
    parts.append(f"- **Conservative (logged but kept):** {stats.conservative_count}")
    recovery_pct = stats.recovery_rate * 100
    parts.append(f"- **Recovered:** {stats.recovered_count} ({recovery_pct:.0f}% recovery rate)")
    parts.append("")
    parts.append("## Source overlap distribution")
    parts.append("")
    parts.append(f"- Min: `{stats.overlap_min:.4f}`")
    parts.append(f"- Max: `{stats.overlap_max:.4f}`")
    parts.append(f"- Mean: `{stats.overlap_mean:.4f}`")
    parts.append(f"- Median: `{stats.overlap_median:.4f}`")
    parts.append("")

    # Per-stage table.
    parts.append("## Per-stage breakdown")
    parts.append("")
    parts.append("| Stage | Total | Dropped | Recovered | Avg overlap |")
    parts.append("|-------|-------|---------|-----------|-------------|")
    for sb in stats.stage_breakdown:
        parts.append(
            f"| `{sb.stage}` | {sb.total} | {sb.dropped} | {sb.recovered} | {sb.avg_overlap:.4f} |"
        )
    parts.append("")

    # Dropped bullets table (all entries, sorted by overlap desc).
    parts.append("## Dropped bullets (sorted by overlap)")
    parts.append("")
    parts.append("| Bullet | Stage | Overlap | Dropped? | Recovered? | Chapter |")
    parts.append("|--------|-------|---------|----------|------------|---------|")
    sorted_entries = sorted(log.entries, key=lambda e: (-e.source_overlap, e.stage, e.bullet))
    for e in sorted_entries:
        bullet_short = e.bullet[:60] + ("..." if len(e.bullet) > 60 else "")
        bullet_escaped = bullet_short.replace("|", "\\|")  # escape pipes in MD table
        chapter_short = (e.chapter or "(unknown)")[:30]
        parts.append(
            f"| {bullet_escaped} | `{e.stage}` | {e.source_overlap:.4f} | "
            f"{'✅' if e.actually_dropped else '⚠️'} | "
            f"{'✅' if e.recovered else '—'} | {chapter_short} |"
        )
    return "\n".join(parts) + "\n"


# ── The format registry + dispatcher ────────────────────────────────────────


QUARANTINE_EXPORT_FORMATS: dict[str, tuple[str, Callable[[QuarantineLog], str]]] = {
    "csv": (
        "CSV — one row per entry, all 10 fields, with a header row (for spreadsheet analysis).",
        export_to_csv,
    ),
    "json": (
        "JSON — the full serialize() output (a list of entry dicts), for programmatic consumption.",
        export_to_json,
    ),
    "markdown": (
        "Markdown — a human-readable report with stats + a table of dropped bullets (for GitHub issues / code reviews).",
        export_to_markdown,
    ),
}


def export_quarantine(log: QuarantineLog, format: str) -> str:
    """Export a QuarantineLog to the named format.

    Args:
        log: the QuarantineLog to export.
        format: one of "csv", "json", "markdown".

    Returns:
        The exported string.

    Raises:
        ValueError: if the format is unknown (lists the available formats).
    """
    if format not in QUARANTINE_EXPORT_FORMATS:
        available = ", ".join(sorted(QUARANTINE_EXPORT_FORMATS.keys()))
        raise ValueError(f"Unknown quarantine export format: {format!r}. Available: {available}.")
    _description, exporter_func = QUARANTINE_EXPORT_FORMATS[format]
    return exporter_func(log)


def list_quarantine_formats() -> list[tuple[str, str]]:
    """List the available quarantine export formats as [(name, description), ...]."""
    return [(name, desc) for name, (desc, _func) in QUARANTINE_EXPORT_FORMATS.items()]


def format_quarantine_formats_for_display(
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format the available quarantine export formats as a multi-line listing."""
    parts: list[str] = []
    parts.append("📤 Available Quarantine Export Formats")
    parts.append("═" * 60)
    for name, (desc, _func) in QUARANTINE_EXPORT_FORMATS.items():
        parts.append(f"  {name:10s}  {desc}")
    parts.append("")
    parts.append(
        "Use `python -m core.summarisation.cli export --drops <FILE> --format "
        "<NAME> [--out FILE]` to export a drops.jsonl file."
    )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out


# Re-export QuarantineEntry so callers can import from this module too.
__all__ = [
    "StageBreakdown",
    "ChapterBreakdown",
    "QuarantineStats",
    "compute_quarantine_stats",
    "format_quarantine_stats_for_display",
    "export_to_csv",
    "export_to_json",
    "export_to_markdown",
    "export_quarantine",
    "QUARANTINE_EXPORT_FORMATS",
    "list_quarantine_formats",
    "format_quarantine_formats_for_display",
    "QuarantineEntry",
]
