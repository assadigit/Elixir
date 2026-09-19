"""V18.10 (Phase 6.2): Per-chapter conversion manifest.

After each chapter completes, write a JSON manifest file capturing the
key conversion metadata: model, context, coverage, phases ran, leak count,
duration. This is an additive output — the existing summary + log files
are unchanged.

The manifest is written to ``<output_dir>/logs/chapter_<N>_manifest.json``
alongside the existing ``drops.jsonl`` and ``quality_report.json``.

Usage (called by the pipeline after each chapter)::

    from core.obs.conversion_manifest import write_chapter_manifest
    write_chapter_manifest(
        output_dir=Path("output/book_title"),
        chapter_index=1,
        chapter_total=1,
        chapter_heading="1 - THE OPENING ARGUMENT",
        model="qwen3:32b",
        num_ctx=26758,
        coverage=0.89,
        phases_ran=["primary", "gap_fill", "scholar_reflection", "post_checks"],
        leak_guard_fires=0,
        post_check_fixes=12,
        post_check_flags=1,
        duration_seconds=1398,
    )
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["write_chapter_manifest", "ChapterManifest"]


class ChapterManifest:
    """V18.10 (Phase 6.2): Per-chapter conversion manifest data structure.

    Captures the key metadata for a single chapter conversion. Written as
    JSON for machine-parseable post-mortem analysis.
    """

    def __init__(
        self,
        chapter_index: int,
        chapter_total: int,
        chapter_heading: str,
        model: str,
        num_ctx: int,
        coverage: float,
        phases_ran: list[str],
        leak_guard_fires: int,
        post_check_fixes: int,
        post_check_flags: int,
        duration_seconds: float,
        bullet_count: int = 0,
        exec_summary_chars: int = 0,
        hallucinations: int = 0,
        timestamp: str | None = None,
    ):
        self.chapter_index = chapter_index
        self.chapter_total = chapter_total
        self.chapter_heading = chapter_heading
        self.model = model
        self.num_ctx = num_ctx
        self.coverage = coverage
        self.phases_ran = phases_ran
        self.leak_guard_fires = leak_guard_fires
        self.post_check_fixes = post_check_fixes
        self.post_check_flags = post_check_flags
        self.duration_seconds = duration_seconds
        self.bullet_count = bullet_count
        self.exec_summary_chars = exec_summary_chars
        self.hallucinations = hallucinations
        self.timestamp = timestamp or datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "timestamp": self.timestamp,
            "chapter_index": self.chapter_index,
            "chapter_total": self.chapter_total,
            "chapter_heading": self.chapter_heading,
            "model": self.model,
            "num_ctx": self.num_ctx,
            "coverage": round(self.coverage, 4),
            "phases_ran": self.phases_ran,
            "leak_guard_fires": self.leak_guard_fires,
            "post_check_fixes": self.post_check_fixes,
            "post_check_flags": self.post_check_flags,
            "duration_seconds": round(self.duration_seconds, 1),
            "duration_minutes": round(self.duration_seconds / 60.0, 2),
            "bullet_count": self.bullet_count,
            "exec_summary_chars": self.exec_summary_chars,
            "hallucinations": self.hallucinations,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string (pretty-printed)."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def write_chapter_manifest(
    output_dir: Path,
    chapter_index: int,
    chapter_total: int,
    chapter_heading: str,
    model: str,
    num_ctx: int,
    coverage: float,
    phases_ran: list[str],
    leak_guard_fires: int,
    post_check_fixes: int,
    post_check_flags: int,
    duration_seconds: float,
    bullet_count: int = 0,
    exec_summary_chars: int = 0,
    hallucinations: int = 0,
) -> Path:
    """Write a per-chapter conversion manifest JSON file.

    Returns the path to the written manifest file.

    The manifest is written to ``<output_dir>/logs/chapter_<N>_manifest.json``.
    If the ``logs/`` subdirectory doesn't exist, it's created.
    """
    manifest = ChapterManifest(
        chapter_index=chapter_index,
        chapter_total=chapter_total,
        chapter_heading=chapter_heading,
        model=model,
        num_ctx=num_ctx,
        coverage=coverage,
        phases_ran=phases_ran,
        leak_guard_fires=leak_guard_fires,
        post_check_fixes=post_check_fixes,
        post_check_flags=post_check_flags,
        duration_seconds=duration_seconds,
        bullet_count=bullet_count,
        exec_summary_chars=exec_summary_chars,
        hallucinations=hallucinations,
    )

    logs_dir = Path(output_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = logs_dir / f"chapter_{chapter_index}_manifest.json"
    # V18.20.2.0 (SWOT A30): atomic write (same-dir temp + fsync +
    # os.replace) — a crash mid-write previously left a truncated manifest
    # that broke post-mortem analysis of exactly the run that crashed.
    # atomic_write_json serializes identically to the old to_json() call
    # (indent=2, ensure_ascii=False) and creates the parent dir itself.
    from utils.atomic_io import atomic_write_json

    atomic_write_json(manifest_path, manifest.to_dict(), indent=2, ensure_ascii=False)

    return manifest_path
