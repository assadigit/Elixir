"""V7.5.0: Centralised output-path resolver — organises conversion outputs

into subfolders instead of a flat dump.

Goal #6 from SESSION_HANDOVER::

    output/MyBook/
    ├── markdown/           ← Full book .md + chapter .md files
    ├── summaries/          ← Book summary + per-chapter summaries
    ├── keypoints/          ← Keypoints + simplified keypoints
    ├── packets/            ← Packets of Knowledge
    ├── podcast/            ← Podcast script(s) + audio
    ├── flashcards/         ← Flashcards .md + .txt
    ├── briefing/           ← Executive briefing
    ├── fa/                 ← Farsi translations
    ├── screenshots/        ← Page screenshots
    ├── graphs/             ← Graph/chart pages
    ├── logs/               ← Conversion log + quality report
    └── .checkpoint.json    ← Resume state (stays at root)

Design notes
------------
- **Backward compatible with resume.**  The checkpoint system
  (``core/pipeline/checkpoint.py``) tracks phases by *status*, not by file
  path, so moving files into subfolders does not break resume.
- **Backward compatible with existing flat layouts.**  ``resolve()`` checks
  both the subfolder location and the legacy flat location, returning
  whichever exists.  This means a book converted under V7.4.0 (flat) can
  still be found by V7.5.0 (subfolders) for re-translation, etc.
- **Lazy creation.**  Subfolders are created on demand via ``dir()``, so a
  conversion that doesn't generate packets won't leave an empty
  ``packets/`` folder.
- The converter sets ``self.paths = OutputPaths(self.output_dir, stem)``
  once in ``__init__`` and then references ``self.paths.X`` everywhere.
"""

from __future__ import annotations

import logging
from pathlib import Path

# Subfolder names (single source of truth)

logger = logging.getLogger(__name__)

SUB_MARKDOWN = "markdown"
SUB_SUMMARIES = "summaries"
SUB_KEYPOINTS = "keypoints"
SUB_PACKETS = "packets"
SUB_PODCAST = "podcast"
SUB_FLASHCARDS = "flashcards"
SUB_BRIEFING = "briefing"
SUB_FA = "fa"
SUB_SCREENSHOTS = "screenshots"
SUB_GRAPHS = "graphs"
SUB_LOGS = "logs"
SUB_OBSIDIAN = "obsidian"
SUB_STUDYGUIDE = "study_guide"
SUB_SOCIAL = "social"
SUB_MINDMAP = "mindmap"
SUB_EVIDENCE = "evidence"  # V10.1.0: Scientific Evidence Map (langextract)
SUB_QA = "qa"  # V10.17.0: Q&A study questions
SUB_GLOSSARY = "glossary"  # V10.20.0: Glossary
SUB_PATTERNS = "patterns"  # V10.20.0: Patterns/Techniques
SUB_CHEATSHEET = "cheatsheet"  # V10.20.0: Cheatsheet
SUB_SKILL = "skill"  # V10.21.0: Agent Skill
SUB_EPUB = "epub"  # V10.35.0: EPUB output
SUB_QUOTE_BANK = "quote_bank"  # V10.35.0: Quote bank


class OutputPaths:
    """Resolves every output path for one book conversion.

    All paths are derived from ``root`` (the per-book output directory) and
    ``stem`` (the input filename without extension, used for top-level files).
    """

    def __init__(self, root: Path, stem: str) -> None:
        self.root = root
        self.stem = stem
        # Legacy flat paths (used for backward-compat lookups + the top-level
        # files that the handover specifies stay at root).
        self.checkpoint = root / ".checkpoint.json"

    # ── helpers ──────────────────────────────────────────────────────────
    def _dir(self, name: str) -> Path:
        """Return ``root/name`` WITHOUT creating it.

        V7.6.0: changed from eager ``mkdir`` to lazy.  Subfolders are now
        created on-demand by the generator that writes into them (via
        ``path.parent.mkdir(parents=True, exist_ok=True)`` before
        ``write_text``).  This prevents empty ``obsidian/``, ``packets/``,
        etc. folders appearing when the user didn't select those outputs.
        """
        return self.root / name

    def _ensure(self, path: Path) -> Path:
        """Ensure the parent dir of ``path`` exists, then return ``path``.

        Convenience for generators: ``self._ensure(path).write_text(...)``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _resolve(self, subfolder: str, filename: str, legacy_flat: str | None = None) -> Path:
        """Prefer the subfolder path; fall back to a legacy flat location.

        Returns the subfolder path (creating the subfolder) if a file exists
        there OR no legacy file exists.  If only the legacy flat file exists,
        returns that path (so old conversions are still readable).  When
        *writing*, always use the subfolder path.
        """
        sub_path = self.root / subfolder / filename
        if sub_path.exists():
            return sub_path
        if legacy_flat:
            flat = self.root / legacy_flat
            if flat.exists():
                return flat
        # Default: the subfolder path (will be created on write).
        return sub_path

    # ── top-level (stay at root per handover) ────────────────────────────
    @property
    def full_markdown(self) -> Path:
        # The full-book .md — handover puts it in markdown/.  But the
        # converter's ConversionResult.full_markdown_path is used by the
        # controller to locate the book dir, so keep a stable path.
        return self._dir(SUB_MARKDOWN) / f"{self.stem}.md"

    @property
    def temp_markdown(self) -> Path:
        return self._dir(SUB_MARKDOWN) / f"{self.stem}.temp.md"

    @property
    def docx(self) -> Path:
        # DOCX is a report bundle — keep at top level for easy access.
        return self.root / f"{self.stem}.docx"

    @property
    def chapters_dir(self) -> Path:
        return self._dir(SUB_MARKDOWN) / "chapters"

    @property
    def chunks_dir(self) -> Path:
        return self._dir(SUB_MARKDOWN) / "chunks"

    # ── summaries ───────────────────────────────────────────────────────
    @property
    def summaries_dir(self) -> Path:
        return self._dir(SUB_SUMMARIES)

    @property
    def book_summary(self) -> Path:
        return self.summaries_dir / f"{self.stem}.summary.md"

    @property
    def chapter_summaries_dir(self) -> Path:
        return self.summaries_dir / "chapters"

    # ── keypoints ───────────────────────────────────────────────────────
    @property
    def keypoints_dir(self) -> Path:
        return self._dir(SUB_KEYPOINTS)

    @property
    def keypoints_md(self) -> Path:
        return self.keypoints_dir / f"{self.stem}.keypoints.md"

    @property
    def keypoints_docx(self) -> Path:
        return self.keypoints_dir / f"{self.stem}.keypoints.docx"

    @property
    def simplified_keypoints(self) -> Path:
        return self.keypoints_dir / f"{self.stem}.keypoints.simplified.md"

    # ── packets of knowledge ────────────────────────────────────────────
    @property
    def packets_dir(self) -> Path:
        return self._dir(SUB_PACKETS)

    # ── podcast ─────────────────────────────────────────────────────────
    @property
    def podcast_dir(self) -> Path:
        return self._dir(SUB_PODCAST)

    def podcast_script(self, book_title: str) -> Path:
        return self.podcast_dir / f"{book_title}.Podcast.md"

    # ── flashcards ──────────────────────────────────────────────────────
    @property
    def flashcards_dir(self) -> Path:
        return self._dir(SUB_FLASHCARDS)

    # ── briefing ────────────────────────────────────────────────────────
    @property
    def briefing_dir(self) -> Path:
        return self._dir(SUB_BRIEFING)

    # ── Farsi translations ──────────────────────────────────────────────
    @property
    def fa_dir(self) -> Path:
        return self._dir(SUB_FA)

    # ── screenshots / graphs ────────────────────────────────────────────
    @property
    def screenshots_dir(self) -> Path:
        return self._dir(SUB_SCREENSHOTS)

    @property
    def graphs_dir(self) -> Path:
        return self._dir(SUB_GRAPHS)

    # ── logs / reports ──────────────────────────────────────────────────
    @property
    def logs_dir(self) -> Path:
        return self._dir(SUB_LOGS)

    @property
    def quality_report(self) -> Path:
        return self.logs_dir / "quality_report.json"

    @property
    def quality_report_previous(self) -> Path:
        return self.logs_dir / "quality_report_previous.json"

    @property
    def ab_comparison(self) -> Path:
        return self.logs_dir / "ab_comparison.json"

    # ── optional outputs (created lazily by their generators) ───────────
    @property
    def obsidian_dir(self) -> Path:
        return self._dir(SUB_OBSIDIAN)

    @property
    def study_guide_dir(self) -> Path:
        return self._dir(SUB_STUDYGUIDE)

    @property
    def social_dir(self) -> Path:
        return self._dir(SUB_SOCIAL)

    @property
    def mindmap_dir(self) -> Path:
        return self._dir(SUB_MINDMAP)

    # V10.1.0: Scientific Evidence Map (langextract grounding output)
    @property
    def evidence_dir(self) -> Path:
        return self._dir(SUB_EVIDENCE)

    # V10.17.0: Q&A study questions
    @property
    def qa_dir(self) -> Path:
        return self._dir(SUB_QA)

    # V10.20.0: Glossary
    @property
    def glossary_dir(self) -> Path:
        return self._dir(SUB_GLOSSARY)

    # V10.20.0: Patterns/Techniques
    @property
    def patterns_dir(self) -> Path:
        return self._dir(SUB_PATTERNS)

    # V10.20.0: Cheatsheet
    @property
    def cheatsheet_dir(self) -> Path:
        return self._dir(SUB_CHEATSHEET)

    # V10.21.0: Agent Skill
    @property
    def skill_dir(self) -> Path:
        return self._dir(SUB_SKILL)

    # V10.35.0: EPUB output
    @property
    def epub_dir(self) -> Path:
        return self._dir(SUB_EPUB)

    # V10.35.0: Quote bank
    @property
    def quote_bank_dir(self) -> Path:
        return self._dir(SUB_QUOTE_BANK)

    # ── misc ────────────────────────────────────────────────────────────
    def footnotes(self, book_title: str) -> Path:
        # Footnotes are reference material — put in markdown/ next to the book.
        return self._dir(SUB_MARKDOWN) / f"{book_title}.footnotes.md"

    def screenshot(self, label: str) -> Path:
        return self.screenshots_dir / f"{label}.jpg"

    def graph_page(self, label: str) -> Path:
        return self.graphs_dir / f"{label}.jpg"
