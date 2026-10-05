"""V0.6.27 (W-l1): translation glossary analytics + export.

Why this exists
---------------
The translation module's ``Glossary`` class (V10.31.0) has
``to_dict``/``from_dict`` (JSON) + ``save``/``load`` (JSON file).
But the operator who wants to use the glossary in a CAT tool
(OmegaT, Trados, memoQ, Wordfast) needs a **TSV or CSV file** —
those tools import glossaries as tab-separated (source TAB translation)
or comma-separated (source, translation, entity_type, frequency) files.
Before V0.6.27, the only export was JSON, which no CAT tool accepts
directly.

And there are NO statistics on the glossary — the operator can't see
at a glance: how many terms are translated vs untranslated? what's
the entity-type distribution (PERSON / ORG / GPE / ...)? what are the
top-N most frequent terms? what's the translation coverage percentage?

This module fills both gaps:

  1. ``compute_glossary_stats(glossary)`` — returns a
     ``GlossaryStats`` dataclass with total_entries / translated_count
     / untranslated_count / coverage_pct / entity_type_distribution /
     top_terms (sorted by frequency).
  2. ``export_to_tsv(glossary)`` — TSV format (source TAB translation),
     the standard CAT-tool glossary format.
  3. ``export_to_csv(glossary)`` — CSV format (source, translation,
     entity_type, frequency), for spreadsheet tools.
  4. ``export_to_json(glossary)`` — wraps the existing ``to_dict()``;
     included for completeness + the format registry.
  5. ``GLOSSARY_EXPORT_FORMATS`` registry + ``export_glossary()``
     dispatcher.
  6. ``format_glossary_stats_for_display()`` — multi-line formatter.

All pure-Python (no PySide6 / no spaCy / no external deps beyond
stdlib ``csv`` + ``json``).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from core.translation.glossary import Glossary, GlossaryEntry

# ── GlossaryStats ───────────────────────────────────────────────────────────


@dataclass
class GlossaryStats:
    """Statistics for a Glossary.

    All counts are computed from the glossary's entries dict. The
    ``coverage_pct`` is (translated_count / total_entries * 100) —
    0 if the glossary is empty.
    """

    total_entries: int = 0
    translated_count: int = 0
    untranslated_count: int = 0
    coverage_pct: float = 0.0
    entity_type_distribution: dict[str, int] = field(default_factory=dict)
    top_terms: list[GlossaryEntry] = field(default_factory=list)
    source_lang: str = "en"
    target_lang: str = "fa"

    @property
    def is_empty(self) -> bool:
        """True iff the glossary has no entries."""
        return self.total_entries == 0


def compute_glossary_stats(glossary: Glossary, top_n: int = 10) -> GlossaryStats:
    """Compute statistics for a Glossary.

    Args:
        glossary: the Glossary to analyze.
        top_n: how many top-frequency terms to include in ``top_terms``
            (default 10; sorted by frequency descending, then source
            alphabetically for determinism).

    Returns:
        A GlossaryStats with all fields populated.
    """
    entries = list(glossary.entries.values())
    total = len(entries)
    if total == 0:
        return GlossaryStats(
            source_lang=glossary.source_lang,
            target_lang=glossary.target_lang,
        )

    translated = sum(1 for e in entries if e.translation.strip())
    untranslated = total - translated
    coverage = (translated / total * 100) if total > 0 else 0.0

    # Entity type distribution — count entries per entity_type.
    type_dist: dict[str, int] = {}
    for e in entries:
        type_dist[e.entity_type] = type_dist.get(e.entity_type, 0) + 1

    # Top terms — sort by frequency (desc), then source (asc) for determinism.
    sorted_entries = sorted(entries, key=lambda e: (-e.frequency, e.source))
    top = sorted_entries[:top_n]

    return GlossaryStats(
        total_entries=total,
        translated_count=translated,
        untranslated_count=untranslated,
        coverage_pct=coverage,
        entity_type_distribution=type_dist,
        top_terms=top,
        source_lang=glossary.source_lang,
        target_lang=glossary.target_lang,
    )


def format_glossary_stats_for_display(
    stats: GlossaryStats,
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format a GlossaryStats as a multi-line string.

    The format::

        📊 Glossary Statistics
        ════════════════════════════════════════════════════════════
        Languages:      en -> fa
        Total entries:  42
        Translated:     35 (83%)
        Untranslated:    7 (17%)

        📑 Entity type distribution:
            PERSON:    12
            ORG:        8
            GPE:        5
            TERM:      17

        🔝 Top 10 terms (by frequency):
            1. Mark Manson (PERSON, 15x) -> مارک منسون
            2. Atomic Habits (WORK_OF_ART, 8x) -> عادت‌های اتمی
            ...

    If the glossary is empty, returns "⚠️ Empty glossary — no stats to show.".
    """
    if stats.is_empty:
        msg = "⚠️ Empty glossary — no stats to show."
        if log:
            log(msg, "WARNING")
        return msg

    parts: list[str] = []
    parts.append("📊 Glossary Statistics")
    parts.append("═" * 60)
    parts.append(f"Languages:      {stats.source_lang} -> {stats.target_lang}")
    parts.append(f"Total entries:  {stats.total_entries}")
    parts.append(f"Translated:     {stats.translated_count} ({stats.coverage_pct:.0f}%)")
    untranslated_pct = 100 - stats.coverage_pct
    parts.append(f"Untranslated:   {stats.untranslated_count} ({untranslated_pct:.0f}%)")
    parts.append("")
    parts.append("📑 Entity type distribution:")
    # Sort by count (desc), then type name (asc) for determinism.
    sorted_types = sorted(
        stats.entity_type_distribution.items(),
        key=lambda x: (-x[1], x[0]),
    )
    for type_name, count in sorted_types:
        parts.append(f"    {type_name:12s}: {count:3d}")
    parts.append("")
    parts.append(f"🔝 Top {len(stats.top_terms)} terms (by frequency):")
    for i, entry in enumerate(stats.top_terms, 1):
        translation_str = entry.translation if entry.translation else "(untranslated)"
        parts.append(
            f"    {i}. {entry.source} ({entry.entity_type}, {entry.frequency}x) "
            f"-> {translation_str}"
        )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out


# ── Exporters ────────────────────────────────────────────────────────────────


def export_to_tsv(glossary: Glossary) -> str:
    """Export a Glossary to TSV (tab-separated values) — the standard
    CAT-tool glossary format.

    Each line: ``source\\ttranslation`` (untranslated terms have an
    empty translation field). Sorted by frequency (desc) then source
    (asc) so the most-important terms appear first.

    Args:
        glossary: the Glossary to export.

    Returns:
        A TSV string. Empty glossary → empty string.
    """
    if not glossary.entries:
        return ""
    entries = sorted(
        glossary.entries.values(),
        key=lambda e: (-e.frequency, e.source),
    )
    lines: list[str] = []
    for e in entries:
        lines.append(f"{e.source}\t{e.translation}")
    return "\n".join(lines) + "\n"


def export_to_csv(glossary: Glossary) -> str:
    """Export a Glossary to CSV (comma-separated values) — for spreadsheet
    tools (Excel, Google Sheets, LibreOffice Calc).

    Columns: source, translation, entity_type, frequency. Includes a
    header row. Sorted by frequency (desc) then source (asc).

    Args:
        glossary: the Glossary to export.

    Returns:
        A CSV string. Empty glossary → just the header row.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["source", "translation", "entity_type", "frequency"])
    entries = sorted(
        glossary.entries.values(),
        key=lambda e: (-e.frequency, e.source),
    )
    for e in entries:
        writer.writerow([e.source, e.translation, e.entity_type, e.frequency])
    return buf.getvalue()


def export_to_json(glossary: Glossary) -> str:
    """Export a Glossary to JSON — wraps the existing ``to_dict()``.

    Included for completeness + the format registry. The JSON format
    is the same as ``Glossary.save()`` writes (source_lang, target_lang,
    entries dict).

    Args:
        glossary: the Glossary to export.

    Returns:
        A JSON string (indented, ensure_ascii=False for non-ASCII
        translations).
    """
    return json.dumps(glossary.to_dict(), indent=2, ensure_ascii=False)


# ── The format registry + dispatcher ────────────────────────────────────────


GLOSSARY_EXPORT_FORMATS: dict[str, tuple[str, Callable[[Glossary], str]]] = {
    "tsv": (
        "TSV (tab-separated) — the standard CAT-tool glossary format (source TAB translation).",
        export_to_tsv,
    ),
    "csv": (
        "CSV (comma-separated) — for spreadsheet tools (source, translation, entity_type, frequency).",
        export_to_csv,
    ),
    "json": (
        "JSON — the full glossary dict (source_lang, target_lang, entries).",
        export_to_json,
    ),
}


def export_glossary(glossary: Glossary, format: str) -> str:
    """Export a Glossary to the named format.

    Args:
        glossary: the Glossary to export.
        format: one of "tsv", "csv", "json".

    Returns:
        The exported string.

    Raises:
        ValueError: if the format is unknown (lists the available formats).
    """
    if format not in GLOSSARY_EXPORT_FORMATS:
        available = ", ".join(sorted(GLOSSARY_EXPORT_FORMATS.keys()))
        raise ValueError(f"Unknown glossary export format: {format!r}. Available: {available}.")
    _description, exporter_func = GLOSSARY_EXPORT_FORMATS[format]
    return exporter_func(glossary)


def list_glossary_formats() -> list[tuple[str, str]]:
    """List the available glossary export formats as [(name, description), ...]."""
    return [(name, desc) for name, (desc, _func) in GLOSSARY_EXPORT_FORMATS.items()]


def format_glossary_formats_for_display(
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format the available glossary export formats as a multi-line listing."""
    parts: list[str] = []
    parts.append("📤 Available Glossary Export Formats")
    parts.append("═" * 60)
    for name, (desc, _func) in GLOSSARY_EXPORT_FORMATS.items():
        parts.append(f"  {name:6s}  {desc}")
    parts.append("")
    parts.append(
        "Use `python -m core.translation.cli export --glossary FILE --format "
        "<NAME> [--out FILE]` to export."
    )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out
