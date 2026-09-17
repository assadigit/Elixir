"""V4.1.0: Obsidian Knowledge Base generator.

Produces a slice of an Obsidian vault: one MOC (Map of Content) index note
plus one note per chapter, interconnected with ``[[wikilinks]]`` and enriched
with YAML frontmatter, tags, and a backlinks section.

Output structure::

    <output_dir>/
      <BookTitle>.Obsidian/
        index.md            ← MOC: links to every chapter note + concept index
        <Chapter 1>.md      ← per-chapter note (frontmatter + summary + bullets)
        <Chapter 2>.md
        ...

The generator is mostly deterministic (no LLM required to produce a usable
vault). One optional LLM call attempts a short cross-chapter synthesis and a
refined tag list; if the call fails or returns nothing useful, a deterministic
fallback is used so the output is always written.

Design notes
------------
* Filenames are sanitised to be Windows-safe (the app targets Windows 10/11).
* Wikilinks use the sanitised filename as the target so they resolve correctly
  inside Obsidian once the folder is dropped into a vault.
* Tags are derived from capitalised terms in chapter headings and key nouns in
  bullets — no external NLP dependency required.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import date
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# ── Windows reserved names we must avoid as filenames ─────────────────────

logger = logging.getLogger(__name__)

_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Domain-term hints — words likely to be meaningful concepts in non-fiction.
# Used to bias tag extraction toward substance rather than stop-words.
_DOMAIN_HINTS = {
    "strategy", "leadership", "marketing", "branding", "psychology",
    "philosophy", "stoicism", "management", "innovation", "creativity",
    "negotiation", "persuasion", "habit", "mindset", "growth", "value",
    "trust", "risk", "decision", "system", "framework", "model", "principle",
    "bias", "heuristic", "cognitive", "behaviour", "behavior", "culture",
    "change", "influence", "network", "feedback", "loop", "leverage",
    "narrative", "storytelling", "audience", "customer", "product", "design",
    "data", "evidence", "research", "theory", "method", "practice", "skill",
    "goal", "outcome", "process", "structure", "pattern", "tradeoff",
}

# Words too common to be useful as standalone tags.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "without", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "as", "at", "by", "from",
    "into", "about", "than", "then", "so", "if", "when", "how", "what", "why",
    "who", "which", "you", "your", "we", "our", "they", "their", "he", "she",
    "his", "her", "not", "no", "yes", "can", "could", "should", "would",
    "will", "may", "might", "must", "do", "does", "did", "have", "has", "had",
    "more", "most", "less", "least", "very", "much", "many", "some", "any",
    "all", "each", "every", "other", "another", "such", "same", "own", "new",
    "old", "first", "last", "next", "one", "two", "three", "also", "only",
    "just", "even", "still", "well", "too", "here", "there", "now", "because", "while", "during", "before", "after", "through", "between",
    "among", "against", "upon", "within", "around", "them",
    "make", "makes", "made", "use", "used", "using", "get", "got", "like",
    "way", "ways", "thing", "things", "people", "person", "time", "times",
}


def _sanitize_filename(name: str, max_len: int = 60) -> str:
    """Make a string safe to use as a filename on Windows + POSIX.

    Collapses runs of non-alphanumeric characters to a single underscore,
    trims, caps length, and avoids Windows reserved names.
    """
    cleaned = re.sub(r"[^\w\s\-]", " ", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "untitled"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip("_")
    if not cleaned:
        cleaned = "untitled"
    # Avoid Windows reserved names (case-insensitive).
    if cleaned.upper() in _WIN_RESERVED:
        cleaned = cleaned + "_"
    return cleaned


def _yaml_str(value: str) -> str:
    """Quote a string for safe YAML frontmatter usage."""
    if value is None:
        return '""'
    # Escape backslashes and double quotes, then wrap in double quotes.
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    # Collapse internal newlines — YAML frontmatter values must be single-line
    # unless using block scalars, which we avoid for simplicity.
    escaped = re.sub(r"\s*\n\s*", "  ", escaped).strip()
    return f'"{escaped}"'


def _yaml_list(items: list[str]) -> str:
    """Render a list of strings as an inline YAML flow sequence."""
    if not items:
        return "[]"
    cleaned = [_yaml_str(it) for it in items if it and it.strip()]
    return "[" + ", ".join(cleaned) + "]"


def _extract_tags_from_heading(heading: str) -> list[str]:
    """Pull candidate concept tags from a chapter heading."""
    if not heading:
        return []
    # Strip common leading numbering: "1. ", "Chapter 3: ", "Part II — "
    h = re.sub(r"^(chapter|part|section|appendix)\s+[ivxlcdm0-9]+[:.\-\s]*",
               "", heading, flags=re.IGNORECASE)
    h = re.sub(r"^\d+([.\-]\d+)*\s*", "", h)
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", h)
    tags: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        # Keep capitalised proper nouns OR domain hints.
        if tok[0].isupper() or low in _DOMAIN_HINTS:
            tag = low.replace("-", "_").replace("'", "")
            if len(tag) >= 3 and tag not in tags:
                tags.append(tag)
    return tags


def _extract_concepts_from_bullets(bullets: list[str]) -> list[tuple[str, int]]:
    """Extract recurring noun-ish terms from bullets, ranked by frequency.

    Returns a list of (term, count) tuples. Used to build the concept index
    in the MOC. Pure heuristic — no NLP dependency.
    """
    freq: Counter = Counter()
    for bp in bullets:
        # Candidate tokens: alphabetic runs of length >= 4, title-cased or
        # domain hints. This favours substance words over glue words.
        tokens = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", bp)
        for tok in tokens:
            low = tok.lower()
            if low in _STOPWORDS:
                continue
            if tok[0].isupper() or low in _DOMAIN_HINTS:
                term = low.replace("-", "_").replace("'", "")
                if len(term) >= 4:
                    freq[term] += 1
    # Keep terms appearing in at least 2 bullets, or all domain-hint terms.
    ranked = [(t, c) for t, c in freq.most_common() if c >= 2]
    if not ranked:
        # Fallback: top singletons so the index is never empty.
        ranked = freq.most_common(15)
    return ranked[:25]


class ObsidianKBGenerator(OutputGeneratorBase):
    """V4.1: Build a linked Obsidian knowledge base from chapter summaries."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate the Obsidian vault slice and return the index.md path."""
        chapters = [s for s in summaries if s.success]
        if not chapters:
            self.log("  ℹ️ Obsidian KB: No chapter summaries to index.", "INFO")
            return None

        self.log(
            f"  🗂️  Building Obsidian KB from {len(chapters)} chapters…", "INFO"
        )

        # ── Prepare the vault folder ──────────────────────────────────────
        safe_book = _sanitize_filename(book_title, max_len=50)
        vault_dir = output_dir / f"{safe_book}.Obsidian"
        try:
            vault_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"  ⚠️ Obsidian KB: cannot create folder {vault_dir}: {e}",
                     "WARNING")
            return None

        today = date.today().isoformat()
        book_tag = re.sub(r"[^a-zA-Z0-9_]", "_", book_title).lower().strip("_")
        if not book_tag:
            book_tag = "book"

        # ── Build per-chapter notes ───────────────────────────────────────
        chapter_link_map: list[tuple[str, str]] = []  # (heading, filename)
        all_bullets: list[str] = []
        all_heading_tags: list[str] = []

        for idx, s in enumerate(chapters, start=1):
            heading = (s.chapter_heading or f"Chapter {idx}").strip()
            fname = _sanitize_filename(heading, max_len=60)
            # Disambiguate duplicate filenames with a numeric suffix.
            existing = {f for _, f in chapter_link_map}
            if fname in existing:
                fname = f"{fname}_{idx}"
            chapter_link_map.append((heading, fname))

            if s.bullet_points:
                all_bullets.extend(s.bullet_points)

            h_tags = _extract_tags_from_heading(heading)
            all_heading_tags.extend(h_tags)

            self._write_chapter_note(
                vault_dir=vault_dir,
                filename=fname,
                heading=heading,
                summary=s,
                book_title=book_title,
                book_tag=book_tag,
                heading_tags=h_tags,
                today=today,
            )

        # ── Concept index (deterministic) ─────────────────────────────────
        concepts = _extract_concepts_from_bullets(all_bullets)

        # ── Optional LLM cross-chapter synthesis ──────────────────────────
        synthesis, llm_tags = self._llm_synthesis(
            chapters, book_title, all_bullets
        )

        # ── Write the MOC index note ──────────────────────────────────────
        index_path = self._write_index_note(
            vault_dir=vault_dir,
            book_title=book_title,
            book_tag=book_tag,
            today=today,
            chapter_link_map=chapter_link_map,
            concepts=concepts,
            heading_tags=all_heading_tags,
            llm_tags=llm_tags,
            synthesis=synthesis,
            chapter_count=len(chapters),
        )

        self.log(
            f"  ✅ Obsidian KB saved to: {vault_dir} "
            f"({len(chapter_link_map)} notes + index)",
            "SUCCESS",
        )
        return index_path

    # ── per-chapter note ──────────────────────────────────────────────────
    def _write_chapter_note(
        self,
        vault_dir: Path,
        filename: str,
        heading: str,
        summary: SummaryResult,
        book_title: str,
        book_tag: str,
        heading_tags: list[str],
        today: str,
    ) -> None:
        """Write a single chapter note with frontmatter + content + backlink."""
        note_path = vault_dir / f"{filename}.md"

        tags = [f"book/{book_tag}"]
        if heading_tags:
            tags.append(f"chapter/{_sanitize_filename(heading, 30).lower()}")
            tags.extend(heading_tags[:5])

        frontmatter = [
            "---",
            f"title: {_yaml_str(heading)}",
            f"aliases: {_yaml_list([heading])}",
            f"source: {_yaml_str(book_title)}",
            "type: chapter-note",
            f"created: {today}",
            f"tags: {_yaml_list(tags)}",
            "---",
        ]

        lines: list[str] = []
        lines.append(f"# {heading}")
        lines.append("")
        lines.append(
            f"> Part of **[[{_sanitize_filename(book_title, 50)}|{book_title}]]**."
        )
        lines.append("")

        if summary.executive_summary:
            lines.append("## Executive Summary")
            lines.append("")
            lines.append(summary.executive_summary.strip())
            lines.append("")

        if summary.thorough_summary:
            lines.append("## Detailed Summary")
            lines.append("")
            lines.append(summary.thorough_summary.strip())
            lines.append("")

        if summary.bullet_points:
            lines.append("## Key Points")
            lines.append("")
            for bp in summary.bullet_points:
                bp_clean = bp.strip().lstrip("-•* ").strip()
                if bp_clean:
                    lines.append(f"- {bp_clean}")
            lines.append("")

        # Backlinks / related section — links back to the MOC and siblings.
        lines.append("## Backlinks")
        lines.append("")
        lines.append(f"- ↑ [[index|Book index ({book_title})]]")
        lines.append("")

        content = "\n".join(frontmatter) + "\n\n" + "\n".join(lines)
        try:
            note_path.write_text(content, encoding="utf-8")
        except Exception as e:
            self.log(
                f"  ⚠️ Obsidian KB: failed to write {note_path.name}: {e}",
                "DEBUG",
            )

    # ── optional LLM synthesis ───────────────────────────────────────────
    def _llm_synthesis(
        self,
        chapters: list[SummaryResult],
        book_title: str,
        all_bullets: list[str],
    ) -> tuple[str, list[str]]:
        """Ask the LLM for a short cross-chapter synthesis + refined tags.

        Returns (synthesis_text, tag_list). On any failure, returns a
        deterministic fallback so the MOC is never empty.
        """
        headings = "\n".join(
            f"- {s.chapter_heading}" for s in chapters[:30] if s.chapter_heading
        )
        bullets_sample = "\n".join(f"- {bp}" for bp in all_bullets[:30])

        prompt = self.prompt_manager.render_template(
            "outputs/obsidian_kb",
            book_title=book_title,
            headings=headings,
            bullets_sample=bullets_sample,
        )
        try:
            resp = self._call_llm(prompt, temperature=0.3, max_tokens=512)
        except Exception as _e:
            resp = None

        synthesis = ""
        tags: list[str] = []
        if resp:
            resp = self._strip_thinking(resp)
            for line in resp.splitlines():
                line = line.strip()
                if line.lower().startswith("synthesis:"):
                    synthesis = line.split(":", 1)[1].strip()
                elif line.lower().startswith("tags:"):
                    raw = line.split(":", 1)[1].strip()
                    tags = [
                        re.sub(r"[^a-z0-9_]", "", t.lower()).strip()
                        for t in raw.split(",")
                    ]
                    tags = [t for t in tags if t][:10]

        if not synthesis:
            synthesis = (
                f"This vault indexes {len(chapters)} chapters of “{book_title}”. "
                "Open any chapter note for its summary and key points; the index "
                "below links them together and lists the recurring concepts."
            )
        if not tags:
            # Deterministic fallback: top heading-derived tags.
            agg: Counter = Counter()
            for s in chapters:
                agg.update(_extract_tags_from_heading(s.chapter_heading))
            tags = [t for t, _ in agg.most_common(8)]
            if not tags:
                # V18.20.3.12 (F821 fix): ``book_tag`` was never defined in this
                # scope (NameError on this last-resort path since the method only
                # receives ``book_title``). Derived here with the SAME book-title
                # tag derivation ``generate()`` uses at :204, so the MOC's
                # ``book/{book_tag}`` and this fallback agree; the original
                # expression and the ``["book"]`` fallback branch are unchanged.
                book_tag = re.sub(r"[^a-zA-Z0-9_]", "_", book_title).lower().strip("_")
                tags = [book_tag.replace(" ", "_")[:20]] if book_tag else ["book"]

        return synthesis, tags

    # ── MOC index note ───────────────────────────────────────────────────
    def _write_index_note(
        self,
        vault_dir: Path,
        book_title: str,
        book_tag: str,
        today: str,
        chapter_link_map: list[tuple[str, str]],
        concepts: list[tuple[str, int]],
        heading_tags: list[str],
        llm_tags: list[str],
        synthesis: str,
        chapter_count: int,
    ) -> Path:
        """Write the MOC index note linking every chapter + concept."""
        index_path = vault_dir / "index.md"

        # Merge tag sources, de-duplicated, preserving order.
        merged_tags: list[str] = [f"book/{book_tag}", "type/moc"]
        seen = {t for t in merged_tags}
        for t in llm_tags + heading_tags:
            if t and t not in seen:
                merged_tags.append(t)
                seen.add(t)
            if len(merged_tags) >= 12:
                break

        frontmatter = [
            "---",
            f"title: {_yaml_str(book_title)}",
            f"aliases: {_yaml_list([book_title])}",
            "type: moc",
            f"created: {today}",
            f"chapters: {chapter_count}",
            f"tags: {_yaml_list(merged_tags)}",
            "---",
        ]

        lines: list[str] = []
        lines.append(f"# {book_title}")
        lines.append("")
        lines.append(f"> Map of Content · {chapter_count} chapters · "
                     f"generated {today}")
        lines.append("")
        lines.append("## Synthesis")
        lines.append("")
        lines.append(synthesis.strip())
        lines.append("")

        # ── Chapter links ──────────────────────────────────────────────────
        lines.append("## Chapters")
        lines.append("")
        for heading, fname in chapter_link_map:
            lines.append(f"- [[{fname}|{heading}]]")
        lines.append("")

        # ── Concept index ──────────────────────────────────────────────────
        lines.append("## Concept Index")
        lines.append("")
        if concepts:
            for term, count in concepts:
                # Use the term as a tag link so it shows up in Obsidian's tag pane.
                lines.append(f"- `#{term}` — appears in {count} key point(s)")
        else:
            lines.append("_No recurring concepts detected._")
        lines.append("")

        # ── Tags block ─────────────────────────────────────────────────────
        lines.append("## Tags")
        lines.append("")
        tag_inline = " ".join(
            f"#{t}" for t in merged_tags
            if not t.startswith("book/") and not t.startswith("type/")
        )
        lines.append(tag_inline if tag_inline else f"#{book_tag}")
        lines.append("")

        content = "\n".join(frontmatter) + "\n\n" + "\n".join(lines)
        index_path.write_text(content, encoding="utf-8")
        return index_path
