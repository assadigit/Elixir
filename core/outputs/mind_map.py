"""V4.1.0: Mind Map generator.

Produces a visual concept map of the book in two forms:

  1. A **Mermaid ``mindmap``** block — renders natively in Obsidian, GitHub,
     VS Code, GitLab, and mermaid.live. Copy the block into any Markdown
     file that supports Mermaid.
  2. A **nested Markdown bullet outline** — for plain-text viewers and
     copy-paste into outliners (Workflowy, Logseq, etc.).

The generator is **fully deterministic** — no LLM calls, no network, no
dependencies. It builds the hierarchy directly from the chapter headings and
key points:

    root((Book Title))
      Chapter 1
        key point 1
        key point 2
      Chapter 2
        ...

Output: ``<BookTitle>.MindMap.md``
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

# Caps to keep the mind map readable. A 200-node mind map is unusable.

logger = logging.getLogger(__name__)

_MAX_CHAPTERS = 25
_MAX_POINTS_PER_CHAPTER = 5
_MAX_NODE_TEXT = 70  # Mermaid node labels should be short

# Characters that break Mermaid mindmap parsing. We strip them rather than
# escape, because Mermaid's quoting rules differ across diagram types and
# stripping is the most robust choice for a generated file.
_MERMAID_STRIP = re.compile(r"[\(\)\[\]\{\}<>\"`|\\]")


def _mermaid_label(text: str, max_len: int = _MAX_NODE_TEXT) -> str:
    """Sanitise a string for use as a Mermaid mindmap node label.

    Strips characters that would break the parser, collapses whitespace,
    and truncates on a word boundary. Uses ASCII "..." (not Unicode "…")
    because Mermaid's parser chokes on the ellipsis character.
    """
    if not text:
        return ""
    # Remove Mermaid-significant characters.
    cleaned = _MERMAID_STRIP.sub("", text)
    # Replace ampersand to avoid HTML-entity confusion.
    cleaned = cleaned.replace("&", "and")
    # V4.7.7: Replace colons — they break Mermaid mindmap node labels.
    cleaned = cleaned.replace(":", " -")
    # Collapse whitespace and newlines.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Remove leading list markers / numbering.
    cleaned = re.sub(r"^[\d]+[\.\)\-]\s*", "", cleaned)
    cleaned = re.sub(r"^[-•*\u2022]\s*", "", cleaned)
    # Truncate on a word boundary — use ASCII "..." not Unicode "…"
    if len(cleaned) > max_len:
        cut = cleaned[:max_len]
        space = cut.rfind(" ")
        if space > max_len * 0.6:
            cut = cut[:space]
        cleaned = cut.rstrip(" ,.;:!?—-") + "..."
    return cleaned


def _indent(level: int, unit: str = "  ") -> str:
    """Return ``level`` indentation units (2 spaces per level for Mermaid)."""
    return unit * level


class MindMapGenerator(OutputGeneratorBase):
    """V4.1: Build a Mermaid mind map + nested outline from keypoints."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate ``BookName.MindMap.md`` and return its path."""
        chapters = [s for s in summaries if s.success]
        if not chapters:
            self.log("  ℹ️ Mind map: No chapter summaries available.", "INFO")
            return None

        # Build the (chapter, [points]) structure, capped for readability.
        structure: list[tuple[str, list[str]]] = []
        for s in chapters[:_MAX_CHAPTERS]:
            heading = (s.chapter_heading or "Untitled").strip()
            points: list[str] = []
            if s.bullet_points:
                for bp in s.bullet_points:
                    bp_clean = bp.strip().lstrip("-•* ").strip()
                    if bp_clean:
                        points.append(bp_clean)
                    if len(points) >= _MAX_POINTS_PER_CHAPTER:
                        break
            structure.append((heading, points))

        if not structure:
            self.log("  ℹ️ Mind map: Nothing to map.", "INFO")
            return None

        self.log(f"  🧠 Building mind map from {len(structure)} chapters…", "INFO")

        mermaid_block = self._build_mermaid(book_title, structure)
        outline = self._build_outline(book_title, structure)

        md = self._assemble_markdown(
            book_title=book_title,
            chapter_count=len(chapters),
            shown_count=len(structure),
            mermaid_block=mermaid_block,
            outline=outline,
        )

        output_path = output_dir / f"{book_title}.MindMap.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        try:
            atomic_write_text(output_path, md, encoding="utf-8")
        except Exception as e:
            self.log(f"  ⚠️ Mind map: failed to write file: {e}", "WARNING")
            return None

        self.log(f"  ✅ Mind map saved to: {output_path}", "SUCCESS")
        return output_path

    # ══════════════════════════════════════════════════════════════════════
    # Builders
    # ══════════════════════════════════════════════════════════════════════

    def _build_mermaid(
        self,
        book_title: str,
        structure: list[tuple[str, list[str]]],
    ) -> str:
        """Render a Mermaid ``mindmap`` block."""
        root_label = _mermaid_label(book_title, max_len=50) or "Book"
        lines: list[str] = ["mindmap", f"  root(({root_label}))"]

        for heading, points in structure:
            chap_label = _mermaid_label(heading, max_len=_MAX_NODE_TEXT)
            if not chap_label:
                continue
            lines.append(f"{_indent(1)}{chap_label}")
            for bp in points:
                pt_label = _mermaid_label(bp, max_len=_MAX_NODE_TEXT)
                if pt_label:
                    lines.append(f"{_indent(2)}{pt_label}")

        return "\n".join(lines)

    def _build_outline(
        self,
        book_title: str,
        structure: list[tuple[str, list[str]]],
    ) -> str:
        """Render a nested Markdown bullet outline (plain-text fallback)."""
        lines: list[str] = [f"- **{book_title}**"]
        for heading, points in structure:
            # Strip leading numbering for a cleaner outline.
            chap = re.sub(r"^[\d]+[\.\)\-]\s*", "", heading).strip()
            lines.append(f"  - {chap}")
            for bp in points:
                bp_clean = bp.strip().lstrip("-•* ").strip()
                if bp_clean:
                    lines.append(f"    - {bp_clean}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════
    # Assembly
    # ══════════════════════════════════════════════════════════════════════

    def _assemble_markdown(
        self,
        book_title: str,
        chapter_count: int,
        shown_count: int,
        mermaid_block: str,
        outline: str,
    ) -> str:
        lines: list[str] = []
        lines.append(f"# Mind Map: {book_title}")
        lines.append("")
        lines.append(
            f"> Visual concept map of {shown_count} of {chapter_count} "
            f"chapters. Top {_MAX_POINTS_PER_CHAPTER} key points per chapter."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Mermaid block
        lines.append("## Mermaid Mind Map")
        lines.append("")
        lines.append(
            "Renders natively in Obsidian, GitHub, VS Code, GitLab, and "
            "[mermaid.live](https://mermaid.live). Paste the block below into "
            "any Markdown file that supports Mermaid."
        )
        lines.append("")
        lines.append("```mermaid")
        lines.append(mermaid_block)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Plain-text outline
        lines.append("## Outline (plain text)")
        lines.append("")
        lines.append("Use this in outliners (Workflowy, Logseq, Roam) or any plain-text editor.")
        lines.append("")
        lines.append(outline)
        lines.append("")

        if shown_count < chapter_count:
            lines.append("---")
            lines.append("")
            lines.append(
                f"_Note: {chapter_count - shown_count} additional chapter(s) "
                f"were omitted to keep the map readable. See the full keypoints "
                f"file for complete coverage._"
            )
            lines.append("")

        return "\n".join(lines)
