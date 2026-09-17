"""V7.8.0: Output Scanner — audits a converted book's output folder.

Given a book's output directory, the scanner answers: "what outputs were
requested, what actually got generated, and what's missing or broken?"

Three signals are combined for each output type:

1. **Checkpoint status** (from ``.checkpoint.json``) — did the phase report
   ``done`` / ``failed`` / ``skipped`` / ``pending``?  This is the
   converter's own record of what happened.

2. **File-system reality** — does the expected file/folder exist, and does
   it have meaningful content (not a 0-byte ghost)?  This catches cases
   where the checkpoint says "done" but the file was deleted, or where the
   generator crashed after creating an empty file.

3. **Requested outputs** (from ``.conversion_config.json``) — did the user
   even ask for this output?  A missing packets folder is only a problem
   if packets were enabled.

The result is a list of :class:`OutputScanResult` entries, each with a
status: ``generated`` / ``missing`` / ``failed`` / ``skipped`` / ``partial``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

# ── Output type definitions ────────────────────────────────────────────────
# Each entry: (key, display_name, category, file_check_fn)
# `file_check_fn(output_dir, stem) -> (exists: bool, size_bytes: int, detail: str)`

logger = logging.getLogger(__name__)

@dataclass
class OutputCheck:
    """How to check for one output type on disk."""
    key: str           # e.g. "full_markdown"
    display_name: str  # e.g. "Full Markdown"
    category: str      # "markdown", "summaries", "outputs", "translation", "logs"
    checkpoint_phase: str  # phase name in .checkpoint.json ("" if none)
    setting_key: str = ""  # setting key in .conversion_config.json ("" if always-on)


def _check_file(path: Path) -> tuple:
    """Return (exists, size, detail) for a single file."""
    if path.exists():
        size = path.stat().st_size
        if size == 0:
            return (True, 0, "0 bytes (empty/ghost)")
        return (True, size, f"{size:,} bytes")
    return (False, 0, "not found")


def _check_dir(path: Path, min_files: int = 1) -> tuple:
    """Return (exists, file_count, detail) for a directory."""
    if path.exists() and path.is_dir():
        files = list(path.glob("**/*"))
        file_count = len([f for f in files if f.is_file()])
        if file_count == 0:
            return (True, 0, "empty folder")
        return (True, file_count, f"{file_count} file(s)")
    return (False, 0, "folder not found")


def _check_glob(pattern: Path) -> tuple:
    """Return (exists, count, detail) for a glob pattern."""
    matches = list(Path(str(pattern)).parent.glob(Path(str(pattern)).name))
    if matches:
        total_size = sum(f.stat().st_size for f in matches if f.is_file())
        return (True, len(matches), f"{len(matches)} file(s), {total_size:,} bytes")
    return (False, 0, "no files match")


# ── All known output types, grouped by category ───────────────────────────
# The check functions are lambdas that take (output_dir, stem) and return
# (exists, count_or_size, detail).

OUTPUT_TYPES: list[OutputCheck] = [
    # ── Markdown ──────────────────────────────────────────────────────────
    OutputCheck("full_markdown", "Full Book Markdown", "markdown", "pdf_extraction"),
    OutputCheck("chapters", "Chapter Files", "markdown", "segmentation"),
    OutputCheck("footnotes", "Footnotes", "markdown", ""),
    # ── Summaries ─────────────────────────────────────────────────────────
    OutputCheck("chapter_summaries", "Per-Chapter Summaries", "summaries", "summarization",
                setting_key="generate_summaries"),
    OutputCheck("book_summary", "Book Summary", "summaries", "summarization",
                setting_key="summarisation.include_book_summary"),
    OutputCheck("keypoints", "Keypoints", "summaries", "keypoints",
                setting_key="summarisation.include_keypoints"),
    OutputCheck("simplified_keypoints", "Simplified Keypoints", "summaries", "simplified_keypoints",
                setting_key="simplified_keypoints_enabled"),
    # ── DOCX ──────────────────────────────────────────────────────────────
    OutputCheck("docx", "DOCX Report", "outputs", "docx",
                setting_key="generate_docx"),
    # ── Output Studio ─────────────────────────────────────────────────────
    OutputCheck("briefing", "Executive Briefing", "outputs", "briefing",
                setting_key="output_briefing"),
    OutputCheck("podcast_script", "Podcast Script(s)", "outputs", "podcast_script",
                setting_key="output_podcast"),
    OutputCheck("packets", "Packets of Knowledge", "outputs", "packets",
                setting_key="output_packets"),
    OutputCheck("flashcards", "Flashcards", "outputs", "flashcards",
                setting_key="output_flashcards"),
    OutputCheck("obsidian", "Obsidian KB", "outputs", "obsidian",
                setting_key="output_obsidian"),
    OutputCheck("study_guide", "Study Guide", "outputs", "study_guide",
                setting_key="output_study_guide"),
    OutputCheck("social", "Social Media Pack", "outputs", "social",
                setting_key="output_social"),
    OutputCheck("mindmap", "Mind Map", "outputs", "mindmap",
                setting_key="output_mindmap"),
    OutputCheck("podcast_audio", "Podcast Audio (TTS)", "outputs", "podcast_audio",
                setting_key="output_tts"),
    # V10.1.0: Scientific Evidence Map (langextract grounding)
    OutputCheck("evidence_map", "Scientific Evidence Map", "outputs", "evidence_map",
                setting_key="output_evidence_map"),
    # ── Translation ───────────────────────────────────────────────────────
    OutputCheck("translation", "Farsi Translation", "translation", "translation"),
    # ── Logs ──────────────────────────────────────────────────────────────
    OutputCheck("quality_report", "Quality Report", "logs", ""),
    OutputCheck("conversion_log", "Conversion Log", "logs", ""),
]


# ── Result dataclass ──────────────────────────────────────────────────────

@dataclass
class OutputScanResult:
    """The scan result for one output type."""
    key: str
    display_name: str
    category: str
    status: str  # "generated" / "missing" / "failed" / "skipped" / "not_requested"
    detail: str  # file size, file count, or error message
    checkpoint_status: str = ""  # raw checkpoint phase status
    path: str = ""  # the checked path (for "open" actions)


@dataclass
class ScanReport:
    """The full scan report for a book output folder."""
    output_dir: Path
    stem: str
    book_title: str = ""
    layout: str = ""  # "v7.5_subfolders" / "legacy_flat" / "unknown"
    results: list[OutputScanResult] = field(default_factory=list)
    checkpoint_found: bool = False
    settings_found: bool = False
    summary_counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def generated_count(self) -> int:
        return self.summary_counts.get("generated", 0)

    @property
    def missing_count(self) -> int:
        return self.summary_counts.get("missing", 0)

    @property
    def failed_count(self) -> int:
        return self.summary_counts.get("failed", 0)


# ── Scanner ───────────────────────────────────────────────────────────────

def detect_layout(output_dir: Path) -> str:
    """Detect whether this is a V7.5+ subfolder layout or legacy flat."""
    if (output_dir / "markdown").is_dir() or (output_dir / "summaries").is_dir():
        return "v7.5_subfolders"
    # Legacy: files directly in output_dir
    if any(output_dir.glob("*.md")) or any(output_dir.glob("*.docx")):
        return "legacy_flat"
    return "unknown"


def detect_stem(output_dir: Path) -> str:
    """Detect the book stem from the output dir contents."""
    # Look for *.md in markdown/ (V7.5) or *.md at root (legacy)
    md_dir = output_dir / "markdown"
    if md_dir.is_dir():
        for f in md_dir.glob("*.md"):
            if not f.name.endswith(".temp.md") and not f.name.endswith(".summary.md"):
                return f.stem
    # Legacy: *.md at root, excluding summaries/keypoints
    for f in output_dir.glob("*.md"):
        name = f.stem
        if not any(name.endswith(s) for s in (".summary", ".keypoints", ".Briefing",
                                               ".Podcast", ".Flashcards", ".temp")):
            return name
    # Fallback: folder name
    return output_dir.name


def load_checkpoint(output_dir: Path) -> dict | None:
    """Load the .checkpoint.json if it exists."""
    cp_path = output_dir / ".checkpoint.json"
    if cp_path.exists():
        try:
            return json.loads(cp_path.read_text(encoding="utf-8"))
        except OSError:
            return None
    return None


def load_settings(output_dir: Path) -> dict | None:
    """Load the .conversion_config.json if it exists."""
    cfg_path = output_dir / ".conversion_config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except OSError:
            return None
    return None


def _check_output_on_disk(key: str, output_dir: Path, stem: str, layout: str) -> tuple:
    """Check if an output exists on disk. Returns (exists, size_or_count, detail, path_str)."""
    # V7.5+ subfolder paths
    if layout == "v7.5_subfolders":
        checks = {
            "full_markdown": lambda: _check_file(output_dir / "markdown" / f"{stem}.md"),
            "chapters": lambda: _check_dir(output_dir / "markdown" / "chapters"),
            "footnotes": lambda: _check_glob(output_dir / "markdown" / f"{stem}.*footnotes*.md"),
            "chapter_summaries": lambda: _check_dir(output_dir / "summaries" / "chapters") if (output_dir / "summaries" / "chapters").exists() else _check_dir(output_dir / "markdown" / "chapters" / "summaries"),
            "book_summary": lambda: _check_file(output_dir / "summaries" / f"{stem}.summary.md") if (output_dir / "summaries").exists() else _check_file(output_dir / f"{stem}.summary.md"),
            "keypoints": lambda: _check_glob(output_dir / "keypoints" / f"{stem}.keypoints*.md") if (output_dir / "keypoints").exists() else _check_glob(output_dir / f"{stem}.keypoints*.md"),
            "simplified_keypoints": lambda: _check_glob(output_dir / "keypoints" / f"{stem}.*simplified*.md") if (output_dir / "keypoints").exists() else _check_glob(output_dir / f"{stem}.*simplified*.md"),
            "docx": lambda: _check_file(output_dir / f"{stem}.docx"),
            "briefing": lambda: _check_glob(output_dir / "briefing" / f"{stem}.Briefing*.md") if (output_dir / "briefing").exists() else _check_glob(output_dir / f"{stem}.Briefing*.md"),
            "podcast_script": lambda: _check_glob(output_dir / "podcast" / f"{stem}.*Podcast*.md") if (output_dir / "podcast").exists() else _check_glob(output_dir / f"{stem}.*Podcast*.md"),
            "packets": lambda: _check_dir(output_dir / "packets") if (output_dir / "packets").exists() else (True, 0, "") if list(output_dir.glob("*Packets*")) else (False, 0, ""),
            "flashcards": lambda: _check_glob(output_dir / "flashcards" / f"{stem}.Flashcards*") if (output_dir / "flashcards").exists() else _check_glob(output_dir / f"{stem}.Flashcards*"),
            "obsidian": lambda: _check_dir(output_dir / "obsidian") if (output_dir / "obsidian").exists() else _check_glob(output_dir / f"{stem}.Obsidian*"),
            "study_guide": lambda: _check_glob(output_dir / "study_guide" / f"{stem}.StudyGuide*") if (output_dir / "study_guide").exists() else _check_glob(output_dir / f"{stem}.StudyGuide*"),
            "social": lambda: _check_glob(output_dir / "social" / f"{stem}.Social*") if (output_dir / "social").exists() else _check_glob(output_dir / f"{stem}.Social*"),
            "mindmap": lambda: _check_glob(output_dir / "mindmap" / f"{stem}.MindMap*") if (output_dir / "mindmap").exists() else _check_glob(output_dir / f"{stem}.MindMap*"),
            "podcast_audio": lambda: _check_glob(output_dir / "podcast" / f"{stem}.*Podcast*.wav") if (output_dir / "podcast").exists() else _check_glob(output_dir / f"{stem}.*Podcast*.wav"),
            # V10.1.0: Scientific Evidence Map
            "evidence_map": lambda: _check_glob(output_dir / "evidence" / f"{stem}.EvidenceMap*") if (output_dir / "evidence").exists() else _check_glob(output_dir / f"{stem}.EvidenceMap*"),
            "translation": lambda: _check_dir(output_dir / "fa") if (output_dir / "fa").exists() else (True, 0, "") if list(output_dir.glob("**/fa/")) else (False, 0, ""),
            "quality_report": lambda: _check_file(output_dir / "logs" / "quality_report.json") if (output_dir / "logs").exists() else _check_file(output_dir / "quality_report.json"),
            "conversion_log": lambda: _check_glob(output_dir / "logs" / "*.conversion.log.md") if (output_dir / "logs").exists() else _check_glob(output_dir / "conversion_logs" / "*.conversion.log.md"),
        }
    else:
        # Legacy flat layout — all files at root
        checks = {
            "full_markdown": lambda: _check_file(output_dir / f"{stem}.md"),
            "chapters": lambda: _check_dir(output_dir / "chapters") if (output_dir / "chapters").exists() else (False, 0, ""),
            "footnotes": lambda: _check_glob(output_dir / f"{stem}.*footnotes*.md"),
            "chapter_summaries": lambda: _check_dir(output_dir / "chapters" / "summaries") if (output_dir / "chapters" / "summaries").exists() else (False, 0, ""),
            "book_summary": lambda: _check_file(output_dir / f"{stem}.summary.md"),
            "keypoints": lambda: _check_glob(output_dir / f"{stem}.keypoints*.md"),
            "simplified_keypoints": lambda: _check_glob(output_dir / f"{stem}.*simplified*.md"),
            "docx": lambda: _check_file(output_dir / f"{stem}.docx"),
            "briefing": lambda: _check_glob(output_dir / f"{stem}.Briefing*.md"),
            "podcast_script": lambda: _check_glob(output_dir / f"{stem}.*Podcast*.md"),
            "packets": lambda: (True, 0, "") if list(output_dir.glob("*Packets*")) else (False, 0, ""),
            "flashcards": lambda: _check_glob(output_dir / f"{stem}.Flashcards*"),
            "obsidian": lambda: _check_glob(output_dir / f"{stem}.Obsidian*"),
            "study_guide": lambda: _check_glob(output_dir / f"{stem}.StudyGuide*"),
            "social": lambda: _check_glob(output_dir / f"{stem}.Social*"),
            "mindmap": lambda: _check_glob(output_dir / f"{stem}.MindMap*"),
            "podcast_audio": lambda: _check_glob(output_dir / f"{stem}.*Podcast*.wav"),
            # V10.1.0: Scientific Evidence Map
            "evidence_map": lambda: _check_glob(output_dir / f"{stem}.EvidenceMap*"),
            "translation": lambda: (True, 0, "") if list(output_dir.glob("**/fa/")) else (False, 0, ""),
            "quality_report": lambda: _check_file(output_dir / "quality_report.json"),
            "conversion_log": lambda: _check_glob(output_dir / "conversion_logs" / "*.conversion.log.md"),
        }

    checker = checks.get(key)
    if checker is None:
        return (False, 0, "unknown output type", "")
    result = checker()
    exists, count, detail = result
    return (exists, count, detail, str(output_dir))


def scan_output_folder(output_dir: Path, log_callback=None) -> ScanReport:
    """Scan a book output folder and return a full report.

    Args:
        output_dir: the per-book output directory (e.g. ``output/Black Swan/``).
        log_callback: optional ``fn(msg, level)`` for diagnostics.

    Returns:
        A :class:`ScanReport` with one :class:`OutputScanResult` per output type.
    """
    log = log_callback or (lambda msg, level: None)
    output_dir = Path(output_dir)

    if not output_dir.exists() or not output_dir.is_dir():
        return ScanReport(output_dir=output_dir, stem="", layout="unknown",
                          results=[], summary_counts={"error": 1})

    layout = detect_layout(output_dir)
    stem = detect_stem(output_dir)
    log(f"  📂 Detected layout: {layout}, stem: {stem}", "DEBUG")

    checkpoint = load_checkpoint(output_dir)
    settings = load_settings(output_dir)
    checkpoint_phases = checkpoint.get("phases", {}) if checkpoint else {}
    log(f"  📋 Checkpoint: {'found' if checkpoint else 'not found'}, "
        f"Settings: {'found' if settings else 'not found'}", "DEBUG")

    # Detect book title from checkpoint or settings
    book_title = ""
    if checkpoint:
        book_title = checkpoint.get("book_name", "")
    if not book_title and settings:
        book_title = Path(settings.get("input_path", "")).stem.replace("_", " ").title()

    results: list[OutputScanResult] = []
    counts: dict[str, int] = {}

    for check in OUTPUT_TYPES:
        # 1. Was this output requested? (from settings)
        requested = True  # default: assume yes if we can't tell
        if check.setting_key and settings:
            # Check the setting_key in settings
            # Some keys are nested (e.g. "summarisation.include_book_summary")
            # The settings file flattens them, so check both forms
            flat_key = check.setting_key.split(".")[-1]
            val = settings.get(check.setting_key, settings.get(flat_key, None))
            if val is not None:
                requested = bool(val)
            # For output_* flags, check the request attrs
            if check.setting_key.startswith("output_"):
                requested = bool(settings.get(check.setting_key, settings.get(check.setting_key.replace("output_", "outputs_"), None)))

        # 2. Checkpoint status
        cp_status = ""
        if check.checkpoint_phase:
            phase_data = checkpoint_phases.get(check.checkpoint_phase, {})
            cp_status = phase_data.get("status", "")

        # 3. File-system reality
        exists, count, detail, path_str = _check_output_on_disk(
            check.key, output_dir, stem, layout
        )

        # 4. Determine final status
        if not requested and check.setting_key:
            status = "not_requested"
        elif cp_status == "failed":
            status = "failed"
            if "error" in checkpoint_phases.get(check.checkpoint_phase, {}):
                detail += f" — error: {checkpoint_phases[check.checkpoint_phase]['error']}"
        elif cp_status == "skipped":
            status = "skipped"
        elif exists and ("0 bytes" in detail or "empty" in detail):
            status = "failed"  # ghost file
            detail = "empty/ghost file"
        elif exists:
            status = "generated"
        elif cp_status == "done":
            status = "missing"  # checkpoint says done but file is gone
            detail = "checkpoint says done but file not found"
        else:
            status = "missing"

        # For always-on outputs (no setting_key), "not_requested" doesn't apply
        if not check.setting_key and status == "not_requested":
            status = "missing" if not exists else "generated"

        results.append(OutputScanResult(
            key=check.key,
            display_name=check.display_name,
            category=check.category,
            status=status,
            detail=detail,
            checkpoint_status=cp_status,
            path=path_str,
        ))
        counts[status] = counts.get(status, 0) + 1

    return ScanReport(
        output_dir=output_dir,
        stem=stem,
        book_title=book_title,
        layout=layout,
        results=results,
        checkpoint_found=checkpoint is not None,
        settings_found=settings is not None,
        summary_counts=counts,
    )
