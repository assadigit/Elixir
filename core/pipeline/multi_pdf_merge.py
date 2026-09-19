"""V10.18.0 (F3): Multi-PDF merge — convert multiple PDFs and produce
a combined summary/keypoints across all of them.

Usage::

    from core.pipeline.multi_pdf_merge import merge_books
    merge_books(
        book_dirs=[Path("output/book1"), Path("output/book2")],
        output_dir=Path("output/merged"),
        log_callback=log,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_books(
    book_dirs: list[Path],
    output_dir: Path,
    log_callback: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Merge summaries + keypoints from multiple book conversions.

    Reads the summaries from each book's output directory, combines them
    into a single unified summary + keypoints file.

    Args:
        book_dirs: list of per-book output directories (each containing
            summaries/ + keypoints/ subfolders)
        output_dir: where to save the merged output
        log_callback: fn(message, level)

    Returns:
        Path to the merged summary file, or None if no books found.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    all_summaries: list[str] = []
    all_keypoints: list[str] = []
    book_titles: list[str] = []

    for book_dir in book_dirs:
        if not book_dir.exists():
            log(f"  ⚠️ Merge: {book_dir.name} not found — skipping.", "WARNING")
            continue

        book_titles.append(book_dir.name)

        # Find the book summary file
        summary_dir = book_dir / "summaries"
        if summary_dir.exists():
            summary_files = sorted(summary_dir.glob("*.summary.md"))
            if summary_files:
                content = summary_files[0].read_text(encoding="utf-8")
                all_summaries.append(f"## From: {book_dir.name}\n\n{content}")

        # Find the keypoints file
        keypoints_dir = book_dir / "keypoints"
        if keypoints_dir.exists():
            kp_files = sorted(keypoints_dir.glob("*.Keypoints.md"))
            if kp_files:
                content = kp_files[0].read_text(encoding="utf-8")
                all_keypoints.append(f"## From: {book_dir.name}\n\n{content}")

    if not all_summaries:
        log("  ℹ️ Merge: no summaries found in any book directory.", "INFO")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write merged summary
    merged_summary = "\n\n---\n\n".join(all_summaries)
    summary_path = output_dir / "Merged_Summary.md"
    summary_path.write_text(
        f"# Merged Summary: {', '.join(book_titles)}\n\n"
        f"**{len(book_titles)} books merged**\n\n---\n\n"
        f"{merged_summary}\n",
        encoding="utf-8",
    )
    log(f"  ✅ Merged summary: {len(book_titles)} books → {summary_path.name}", "SUCCESS")

    # Write merged keypoints
    if all_keypoints:
        merged_kp = "\n\n---\n\n".join(all_keypoints)
        kp_path = output_dir / "Merged_Keypoints.md"
        kp_path.write_text(
            f"# Merged Keypoints: {', '.join(book_titles)}\n\n"
            f"**{len(book_titles)} books merged**\n\n---\n\n"
            f"{merged_kp}\n",
            encoding="utf-8",
        )
        log(f"  ✅ Merged keypoints: {len(all_keypoints)} books → {kp_path.name}", "SUCCESS")

    return summary_path
