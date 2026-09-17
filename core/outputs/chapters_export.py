"""V13.23.0: Chapters export — the canonical intermediate file for Packets.

Generates and parses ``{Book}.Chapters.md`` — a structured markdown file that
consolidates per-chapter executive summaries + bullet points into a single
artifact.

WHY THIS FILE EXISTS
--------------------
The author already organized related concepts into chapters.  Chapter-aligned
Packets mode (V13.23.0) uses this natural grouping instead of lossy cross-
chapter semantic clustering.  This file is:

1. **A human-readable artifact** — the user can inspect what the summarizer
   produced before packets run.
2. **The canonical input for the standalone Packets tool** — load this file
   in PacketsToolDialog to re-run packets without re-converting the book.
3. **A verification checkpoint** — the TOC at the top lets the model/Python
   confirm that detected chapters match the table of contents.
4. **A fallback source** — when a chapter has too few bullets for a good
   packet (< MIN_BULLETS_PER_PACKET), the exec summary is used as
   supplementary context instead of hallucinating.

FILE FORMAT
-----------
    # {Book Title}

    ## Table of Contents

    1. {Chapter 1 heading}
    2. {Chapter 2 heading}
    ...

    ---

    ## {Chapter 1 heading}

    ### Executive Summary

    {executive summary text}

    ### Bullet Points

    - bullet 1
    - bullet 2
    ...

    ---

    ## {Chapter 2 heading}

    ### Executive Summary

    ...

    ### Bullet Points

    - ...
"""
from __future__ import annotations

import re
from pathlib import Path

from core.models import SummaryResult
# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text


def write_chapters_md(
    summaries: list[SummaryResult],
    book_title: str,
    output_path: Path,
) -> Path:
    """Write the consolidated chapters markdown file.

    Args:
        summaries: List of SummaryResult (one per chapter).
        book_title: Book title for the file header.
        output_path: Full path to write (e.g. ``output_dir / f"{title}.Chapters.md"``).

    Returns:
        The path that was written.
    """
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────
    lines.append(f"# {book_title}")
    lines.append("")

    # ── Table of Contents ─────────────────────────────────────────────────
    lines.append("## Table of Contents")
    lines.append("")
    for i, s in enumerate(summaries, 1):
        heading = (s.chapter_heading or f"Chapter {i}").strip()
        lines.append(f"{i}. {heading}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Per-chapter sections ──────────────────────────────────────────────
    for i, s in enumerate(summaries, 1):
        heading = (s.chapter_heading or f"Chapter {i}").strip()
        lines.append(f"## {heading}")
        lines.append("")

        # Executive Summary
        lines.append("### Executive Summary")
        lines.append("")
        exec_text = (s.executive_summary or "").strip()
        if exec_text:
            lines.append(exec_text)
        else:
            lines.append("*(No executive summary available for this chapter.)*")
        lines.append("")

        # Bullet Points
        lines.append("### Bullet Points")
        lines.append("")
        if s.bullet_points:
            for bullet in s.bullet_points:
                clean = bullet.strip().lstrip("-*+•·▪◦‣ ").strip()
                if clean:
                    lines.append(f"- {clean}")
        else:
            lines.append("*(No bullet points extracted for this chapter.)*")
        lines.append("")
        lines.append("---")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, "\n".join(lines), encoding="utf-8")
    return output_path


def read_chapters_md(path: Path) -> tuple[str, list[SummaryResult]]:
    """Parse a chapters markdown file back into (book_title, summaries).

    This is the inverse of :func:`write_chapters_md`.  Used by the standalone
    PacketsToolDialog to load a ``.Chapters.md`` file.

    Returns:
        ``(book_title, summaries)`` where ``summaries`` is a list of
        SummaryResult (one per chapter section found).

    Raises:
        ValueError: if the file doesn't look like a chapters-md file (no
            ``# `` title line and no ``## `` chapter headings).
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise ValueError("File is empty.")

    # ── Extract book title (first # heading) ──────────────────────────────
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    book_title = title_match.group(1).strip() if title_match else Path(path).stem

    # ── Extract chapter sections (## headings, skip "## Table of Contents") ──
    # Split on ## headings, filter out the TOC section.
    chapter_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(chapter_pattern.finditer(text))

    # Filter out "Table of Contents" heading
    chapter_starts = [
        m for m in matches
        if m.group(1).strip().lower() != "table of contents"
    ]

    if not chapter_starts:
        # Fallback: no chapter structure found — treat whole file as 1 chapter
        bullets = _extract_bullets_from_text(text)
        if not bullets:
            raise ValueError(
                "No chapter sections (## headings) and no bullet points found. "
                "Expected format: # Title, ## Chapter, ### Executive Summary, "
                "### Bullet Points."
            )
        return book_title, [SummaryResult(
            chapter_heading=book_title,
            executive_summary="",
            thorough_summary="",
            bullet_points=bullets,
            success=True,
        )]

    summaries: list[SummaryResult] = []
    for i, match in enumerate(chapter_starts):
        heading = match.group(1).strip()
        # Content = from end of this heading to start of next ## heading (or EOF)
        start = match.end()
        end = chapter_starts[i + 1].start() if i + 1 < len(chapter_starts) else len(text)
        section_text = text[start:end]

        # Parse exec summary (between ### Executive Summary and next ###)
        exec_summary = _extract_section(section_text, "Executive Summary")

        # Parse bullet points (between ### Bullet Points and next ### or ---)
        bullets_text = _extract_section(section_text, "Bullet Points")
        bullets = _extract_bullets_from_text(bullets_text)

        if not bullets and not exec_summary:
            # Skip empty sections
            continue

        summaries.append(SummaryResult(
            chapter_heading=heading,
            executive_summary=exec_summary,
            thorough_summary="",
            bullet_points=bullets,
            success=True,
        ))

    if not summaries:
        raise ValueError("No valid chapter sections with content found.")

    return book_title, summaries


def _extract_section(text: str, section_name: str) -> str:
    """Extract the text between ``### {section_name}`` and the next ``###`` or ``---`` or EOF."""
    pattern = re.compile(
        rf"^###\s+{re.escape(section_name)}\s*\n(.*?)(?=^###\s|^---\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_bullets_from_text(text: str) -> list[str]:
    """Extract bullet lines from markdown text (handles -, *, +, •, numbered)."""
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Markdown bullet markers
        m = re.match(r"^[-*+•·▪◦‣]\s+(.+)$", stripped)
        if m:
            clean = m.group(1).strip()
            if clean and len(clean) > 3:
                bullets.append(clean)
            continue
        # Numbered list
        m = re.match(r"^\d+[.):]\s+(.+)$", stripped)
        if m:
            clean = m.group(1).strip()
            if clean and len(clean) > 3:
                bullets.append(clean)
    return bullets
