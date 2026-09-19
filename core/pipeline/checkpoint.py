"""V7.0.0: Checkpoint/Resume system for conversion pipeline.

Tracks which phases completed successfully so that if the app crashes or
power goes out, the user can resume from where it stopped — skipping
completed phases.

The checkpoint file (.checkpoint.json) lives in the output directory::

    {
        "book_name": "Agent of Influence",
        "input_path": "G:\\Docs\\Agent of Influence.pdf",
        "created_at": "2026-07-19T03:37:55",
        "updated_at": "2026-07-19T04:01:19",
        "phases": {
            "pdf_extraction": {"status": "done", "pages": 19, "elapsed_s": 21.2},
            "segmentation": {"status": "done", "segments": 2, "elapsed_s": 0.5},
            "summarization": {"status": "done", "chapters": 2, "elapsed_s": 743.0},
            "keypoints": {"status": "done", "count": 41, "elapsed_s": 30.0},
            "simplified_keypoints": {"status": "done", "count": 26, "elapsed_s": 330.0},
            "docx": {"status": "done", "elapsed_s": 0.1},
            "briefing": {"status": "done", "elapsed_s": 47.0},
            "podcast_script": {"status": "done", "scripts": 1, "elapsed_s": 188.0},
            "flashcards": {"status": "done", "cards": 41, "elapsed_s": 45.0},
            "podcast_audio": {"status": "failed", "error": "Piper binary not found", "elapsed_s": 0.5},
            "obsidian": {"status": "skipped"},
            "study_guide": {"status": "skipped"},
            "social": {"status": "skipped"},
            "mindmap": {"status": "skipped"},
            "rag_indexing": {"status": "skipped"},
            "screenshots": {"status": "skipped"},
            "graphs": {"status": "skipped"},
            "translation": {"status": "pending"}
        },
        "version": "7.0.0"
    }

The wizard checks for this file on startup and offers "Resume from where
it stopped?" if found.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PhaseStatus:
    """Status of a single conversion phase."""

    status: str = "pending"  # "pending", "in_progress", "done", "failed", "skipped"
    elapsed_s: float = 0.0
    error: str = ""
    # Phase-specific metadata (pages, chapters, count, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    """Conversion checkpoint — tracks progress across all phases."""

    book_name: str = ""
    input_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    version: str = "13.25.0"  # V13.25.0: bumped from "7.0.0" — schema is stable
    phases: dict[str, PhaseStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")
        # Initialize all known phases as pending
        if not self.phases:
            for phase in _ALL_PHASES:
                self.phases[phase] = PhaseStatus(status="pending")

    @property
    def checkpoint_path(self) -> Path:
        return self._output_dir / ".checkpoint.json"

    def set_output_dir(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def mark_done(self, phase: str, elapsed_s: float = 0.0, **metadata) -> None:
        """Mark a phase as completed successfully."""
        if phase not in self.phases:
            self.phases[phase] = PhaseStatus()
        self.phases[phase].status = "done"
        self.phases[phase].elapsed_s = elapsed_s
        self.phases[phase].metadata.update(metadata)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        self.save()

    def mark_progress(self, phase: str, **metadata) -> None:
        """V18.20.3.0: Record in-phase progress metadata WITHOUT marking done.

        Used by the incremental chapter-checkpoint saver (e.g.
        ``mark_progress("summarization", chapters_done=4, chapters_total=10)``)
        so a crash mid-phase leaves a visible record of how far the run got.

        Status is deliberately KEPT resumable: "pending" stays "pending"
        (and "failed" stays "failed") — ``should_run()`` keeps returning
        True, so a resume re-enters the phase and the chapter-resume
        sentinels (``<!-- COMPLETE -->`` markers) decide which chapters to
        skip. This preserves the V18.20.2.0 (SWOT A15) invariant: a partial
        run must never look phase-complete. "done"/"skipped" are untouched
        (late progress calls after phase completion are no-ops on status).
        """
        if phase not in self.phases:
            self.phases[phase] = PhaseStatus()
        ps = self.phases[phase]
        if ps.status in ("pending", "in_progress"):
            ps.status = "pending"  # keep resumable
        ps.metadata.update(metadata)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        self.save()

    def mark_failed(self, phase: str, error: str, elapsed_s: float = 0.0) -> None:
        """Mark a phase as failed."""
        if phase not in self.phases:
            self.phases[phase] = PhaseStatus()
        self.phases[phase].status = "failed"
        self.phases[phase].error = error
        self.phases[phase].elapsed_s = elapsed_s
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        self.save()

    def mark_skipped(self, phase: str) -> None:
        """Mark a phase as skipped (not enabled)."""
        if phase not in self.phases:
            self.phases[phase] = PhaseStatus()
        self.phases[phase].status = "skipped"
        self.save()

    def is_done(self, phase: str) -> bool:
        """Check if a phase is completed."""
        return self.phases.get(phase, PhaseStatus()).status == "done"

    def is_failed(self, phase: str) -> bool:
        """Check if a phase failed."""
        return self.phases.get(phase, PhaseStatus()).status == "failed"

    def is_skipped(self, phase: str) -> bool:
        """Check if a phase was skipped."""
        return self.phases.get(phase, PhaseStatus()).status == "skipped"

    def should_run(self, phase: str) -> bool:
        """Check if a phase should run (not done, not skipped)."""
        status = self.phases.get(phase, PhaseStatus()).status
        return status in ("pending", "failed")

    def get_resume_point(self) -> str | None:
        """Return the name of the first phase that should run (resume point).

        Returns None if all phases are done/skipped.
        """
        for phase in _ALL_PHASES:
            if self.should_run(phase):
                return phase
        return None

    def get_summary(self) -> str:
        """Return a human-readable summary of the checkpoint."""
        lines = []
        done = sum(1 for p in self.phases.values() if p.status == "done")
        failed = sum(1 for p in self.phases.values() if p.status == "failed")
        skipped = sum(1 for p in self.phases.values() if p.status == "skipped")
        pending = sum(1 for p in self.phases.values() if p.status == "pending")
        lines.append(
            f"Checkpoint: {done} done, {failed} failed, {skipped} skipped, {pending} pending"
        )
        for phase in _ALL_PHASES:
            ps = self.phases.get(phase, PhaseStatus())
            if ps.status == "done":
                meta = (
                    f" ({', '.join(f'{k}={v}' for k, v in ps.metadata.items())})"
                    if ps.metadata
                    else ""
                )
                lines.append(f"  ✅ {phase}: done{meta} [{ps.elapsed_s:.1f}s]")
            elif ps.status == "failed":
                lines.append(f"  ❌ {phase}: FAILED — {ps.error}")
            elif ps.status == "skipped":
                lines.append(f"  ⏭️ {phase}: skipped")
            else:
                lines.append(f"  ⏳ {phase}: pending")
        return "\n".join(lines)

    def save(self) -> None:
        """Save the checkpoint to the output directory."""
        if not hasattr(self, "_output_dir"):
            return
        try:
            data = {
                "book_name": self.book_name,
                "input_path": self.input_path,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "version": self.version,
                "phases": {k: asdict(v) for k, v in self.phases.items()},
            }
            self._output_dir.mkdir(parents=True, exist_ok=True)
            # V9.0.0: atomic write — prevents corrupted checkpoint on crash
            from utils.atomic_io import atomic_write_json

            atomic_write_json(self.checkpoint_path, data, indent=2, ensure_ascii=False)
        except Exception as e:
            # V10.4.0 (Phase 6A-4): Log the failure (e.g. disk-full) instead
            # of silently swallowing it.  Checkpoint saving still never
            # crashes the conversion (resume capability is best-effort), but
            # the user now sees WHY the checkpoint wasn't saved — previously
            # a full disk silently broke resume with no diagnostic.
            logger.warning(
                f"[Checkpoint] Could not save checkpoint state: {e}. "
                f"Resume capability may be unavailable for this run."
            )

    @classmethod
    def load(cls, output_dir: Path) -> Checkpoint | None:
        """Load a checkpoint from the output directory, or None if not found."""
        cp_path = output_dir / ".checkpoint.json"
        if not cp_path.exists():
            return None
        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            cp = cls(
                book_name=data.get("book_name", ""),
                input_path=data.get("input_path", ""),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                version=data.get("version", "7.0.0"),
            )
            cp._output_dir = output_dir
            # Load phase statuses
            for phase_name, phase_data in data.get("phases", {}).items():
                cp.phases[phase_name] = PhaseStatus(
                    status=phase_data.get("status", "pending"),
                    elapsed_s=phase_data.get("elapsed_s", 0.0),
                    error=phase_data.get("error", ""),
                    metadata=phase_data.get("metadata", {}),
                )
            return cp
        except Exception as _e:
            return None

    @classmethod
    def check_for_existing(cls, output_dir: Path) -> Checkpoint | None:
        """Check if a checkpoint exists in the output directory.

        This is called by the wizard on startup to offer resume.
        """
        return cls.load(output_dir)


# ── All known phases in execution order ─────────────────────────────────────

_ALL_PHASES = [
    "pdf_extraction",
    "segmentation",
    "summarization",
    "keypoints",
    "simplified_keypoints",
    "docx",
    "briefing",
    "podcast_script",
    "flashcards",
    "obsidian",
    "study_guide",
    "social",
    "mindmap",
    "packets",  # V13.25.0: was missing from the original list
    "podcast_audio",
    "rag_indexing",
    "screenshots",
    "graphs",
    "translation",
]
